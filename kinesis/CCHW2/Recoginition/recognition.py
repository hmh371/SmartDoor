import boto3
import json
import cv2      # *** Before upload to lambda function, I have to install the dependencies on the local path
import base64
import random
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr


def generate_otp(table):
    otp = int(random.random() * 1000000)
    passcode = table.scan(FilterExpression=Attr('otp').eq(otp))
    while passcode['Count']:
        otp = int(random.random() * 1000000)
        passcode = table.scan(FilterExpression=Attr('otp').eq(otp))
    return otp


def send_sns(message, phone_num):
    sns = boto3.client('sns')
    response = sns.publish(
        PhoneNumber=phone_num,
        Message=message,
        MessageStructure='string'
    )
    return response


def video_process(video_path, image_path):
    name = video_path
    vc = cv2.VideoCapture(video_path)
    c = 1
    if vc.isOpened():
        ret, frame = vc.read()
    else:
        ret = False
    while ret:
        ret, frame = vc.read()
        if c == 2:
            # Saving the image
            cv2.imwrite(image_path, frame)

            # *** I have to save the image to the S3, DB and Face collection
        c = c + 1
        cv2.waitKey(1)
    vc.release()


def getOjectfromS3(bucket, key):
    s3 = boto3.client("s3")

    response = s3.get_object(
        Bucket=bucket,
        Key=key
    )
    return response


def lambda_handler(event, context):
    # TODO implement

    """
    read the object from Kinesis Data Streams
    """
    print(event['Records'])
    for each_record in event['Records']:
        # The data is encoded by base64. Decode it first
        payload = json.loads(base64.b16decode(each_record['kinesis']['data']))
        print(payload)

        dynamodb = boto3.resource('dynamodb')
        passcode_table = dynamodb.Table('passcodes')
        visitor_table = dynamodb.Table('visitors')

        # If FaceSearchResponse and MatchedFaces exists, the video can find the face matching with collections
        if payload['FaceSearchResponse']:
            face_search_response = payload['FaceSearchResponse']
            if face_search_response[0]['MatchedFaces']:

                print("Video visitor's face is matched. This is a known visitors.")

                match_faces = face_search_response[0]['MatchedFaces']
                similarity = match_faces[0]['Similarity']
                faceId = match_faces[0]['Face']['FaceId']

                # Send otp to verify his
                otp = generate_otp(passcode_table)
                passcode = passcode_table.scan(FilterExpression=Attr('faceId').eq(faceId))

                # If this face is in the dynamodb
                if passcode['Items']:
                    original_time = datetime.strptime(passcode['Items'][0]['timeStamp'], "%m-%d-%Y %H:%M:%S")
                    current_time = datetime.now()
                    seconds = (current_time - original_time).total_seconds()
                    minutes = divmod(seconds, 60)[0]
                    if minutes > 5:
                        print("update the item in database Now!")
                        passcode_table.update_item(
                            Key={
                                'faceId':faceId,
                            },
                            AttributeUpdates={
                                'passcode': {
                                    'Value': otp,
                                    'Action': 'PUT'
                                },
                                'timeStamp': {
                                    'Value': current_time.strftime("%m-%d-%Y %H:%M:%S"),
                                    'Action': 'PUT'
                                }
                            }
                        )

                    # If it is still in 5 minutes, We just wait
                    else:
                        continue

                # If this face is not in the db, we have to add it into the database
                else:
                    passcode_table.put_item(
                        Item={
                            'faceId': faceId,
                            'passcode': otp,
                            'timeStamp': datetime.now().strftime("%m-%d-%Y %H:%M:%S")
                        }
                    )

                visitor = visitor_table.scan(FilterExpression=Attr('faceId').eq(faceId))
                phone_num = visitor['Item'][0]['phoneNumber']

                response_sns_text = 'Welcome! here is the one-time passcode: {} \nIt would be expired in 5 minutes!'.format(otp)

                response = send_sns(response_sns_text, phone_num)

                return response


            else: # If there is no matched face in the collection

                """
                Verify unknown visitors
                """

                print("The visitor is not a known visitor.")

                FragmentNumber = payload['InputInformation']['KinesisVideo']['FragmentNumber']

                kvs = boto3.client('kinesisvideo')
                data_endpoint = kvs.get_data_endpoint(
                    StreamARN="arn:aws:kinesisvideo:us-east-1:971614317796:stream/smartdoorkvs/1587152393750",
                    APIName="GET_MEDIA"
                )


                endpoint = data_endpoint

                kvs_video = boto3.client('kinesis-video-media', endpoint_url=endpoint)
                kvs_stream = kvs_video.get_media(
                    StreamARN="arn:aws:kinesisvideo:us-east-1:971614317796:stream/smartdoorkvs/1587152393750",
                    StartSelector={
                        'StartSelectorType': 'FRAGMENT_NUMBER', 'AfterFragmentNumber': FragmentNumber
                    }
                )
                print(kvs_stream)

                file_path = '/tmp/' + datetime.now().strftime("%m-%d-%Y-%H-%M-%S") + '.mkv'
                image_name = datetime.now().strftime("%m-%d-%Y-%H-%M-%S") + '.jpg'
                image_path = '/tmp/' + image_name

                with open(file_path, 'wb') as f:
                    streamBody = kvs_stream['Payload'].read(1024*2048)
                    f.write(streamBody)
                f.close()

                # Use openCV to get a frame from the stored video
                video_process(file_path, image_path)
                print("Successfully catch the frame, and write it to /tmp dir")

                s3 = boto3.client('s3')
                s3_bucket = "visitors-face"

                s3.upload_file(
                    image_path,
                    s3_bucket,
                    image_name
                )



                """
                Send the email notification to the owner
                """

                # 这里没写完


                ses = boto3.client("ses")


                Message_details = "These is a unknown visitor. Please verify his identity."
                Message_photo = ""

                response = ses.send_email(
                    Source='rz1535@nyu.edu',
                    Destination = {
                        'ToAddress':[
                            'rz1535@nyu.edu',
                        ]
                    },
                    Message={
                        'Subject': {
                            'Data': 'Unkown visitor'
                        },
                        'Body': {
                            'Html': {
                                'Data': Message_details + Message_photo
                            }
                        }
                    }
                )
                print("Image uploaded!")
                return response

        return "No face detected!"
    return "That is an end!"






                # all_objects = s3.list_objects(Bucket=s3_bucket)['Content']
                #
                # time_now = datetime.now()
                # threshold = 180
                #
                # canInsert = True
                #
                # for each_object in all_objects:
                #     file_name = each_object['Key']
                #     print(file_name)
                #     if not file_name.startswith('photo'):
                #         continue
                #
                #















