import json
import base64
import boto3
import sys
sys.path.insert(1, '/opt')
import cv2
import random
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime

def generate_otp(table):
    otp = int(random.random() * 1000000)
    passcode = table.scan(FilterExpression=Attr('otp').eq(otp))
    while passcode['Count']:
        otp = int(random.random() * 1000000)
        passcode = table.scan(FilterExpression=Attr('otp').eq(otp))
    return otp

def send_sns(message, phone_num):
    messagingClient = boto3.client('sns')
    response = messagingClient.publish(
        PhoneNumber=phone_num,
        Message=message,
        MessageStructure='string',
    )
    return response

def lambda_handler(event, context):
    # TODO implement
    print(event['Records'])
    for record in event['Records']:
        payload = json.loads(base64.b64decode(record['kinesis']['data']))
        #ProducerTimestamp = record['InputInformation']['KinesisVideo']['ProducerTimestamp']
        #FrameOffsetInSeconds = record['InputInformation']['KinesisVideo']['FrameOffsetInSeconds']
        print(payload)

        dynamodb = boto3.resource('dynamodb')
        passcode_table = dynamodb.Table('passcodes')
        visitor_table = dynamodb.Table('visitors')

        if payload['FaceSearchResponse']:
            if payload['FaceSearchResponse'][0]['MatchedFaces']:
                print("verified")
                similarity = payload['FaceSearchResponse'][0]['MatchedFaces'][0]['Similarity']
                faceId = payload['FaceSearchResponse'][0]['MatchedFaces'][0]['Face']['FaceId']

                #return similarity
                otp = generate_otp(passcode_table)
                passcode = passcode_table.scan(FilterExpression=Attr('faceId').eq(faceId))
                if passcode['Items']:
                    original_time = datetime.strptime(passcode['Items'][0]['timeStamp'], "%m-%d-%Y %H:%M:%S")
                    current_time = datetime.now()
                    seconds = (current_time - original_time).total_seconds()
                    minutes = divmod(seconds, 60)[0]
                    if minutes > 5:
                        print("update")
                        passcode_table.update_item(
                            Key={
                                'faceId': faceId
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

                    else:
                        continue
                else:
                    passcode_table.put_item(
                        Item={
                            'faceId': faceId,
                            'passcode': otp,
                            'timeStamp': datetime.now().strftime("%m-%d-%Y %H:%M:%S")
                        }
                    )

                visitor = visitor_table.scan(FilterExpression=Attr('faceId').eq(faceId))
                phone_num = visitor['Items'][0]['phoneNumber']

                response_sns_text = 'Here is your one-time passcode: {otp} \nIt will expire in 5 minutes.\n'.format(
                    otp=otp
                )

                response = send_sns(response_sns_text, phone_num)

                return response

            else:

                print("unverified")
                FragmentNumber = payload['InputInformation']['KinesisVideo']['FragmentNumber']
                kvs_client = boto3.client('kinesisvideo')
                kvs_data_pt = kvs_client.get_data_endpoint(
                    StreamARN="arn:aws:kinesisvideo:us-east-1:828504888294:stream/sanyang-KVS/1573761060179",#@@@
                    APIName='GET_MEDIA'
                )

                print(kvs_data_pt)

                end_pt = kvs_data_pt['DataEndpoint']
                kvs_video_client = boto3.client('kinesis-video-media', endpoint_url=end_pt, region_name='us-east-1')
                kvs_stream = kvs_video_client.get_media(
                    StreamARN="arn:aws:kinesisvideo:us-east-1:828504888294:stream/sanyang-KVS/1573761060179",#@@@
                    StartSelector={'StartSelectorType': 'FRAGMENT_NUMBER', 'AfterFragmentNumber': FragmentNumber} # to keep getting latest available chunk on the stream
                )
                print(kvs_stream)

                with open('/tmp/stream.mkv', 'wb') as f:
                    streamBody = kvs_stream['Payload'].read(1024*2048) # reads min(16MB of payload, payload size) - can tweak this
                    f.write(streamBody)
                f.close()

                # use openCV to get a frame
                print("write video to tmp")
                cap = cv2.VideoCapture('/tmp/stream.mkv')
                print("capture with cv2")
                # use some logic to ensure the frame being read has the person, something like bounding box or median'th frame of the video etc
                unverified_bucket = 'unverifiedphoto'
                unverified_photo = 'photo-'+ datetime.now().strftime("%m-%d-%Y-%H-%M-%S") + '.jpg'

                ret, frame = cap.read()
                print("read frame")
                
                if frame is None:
                    continue
                

                s3_client = boto3.client('s3')

                all_objects = s3_client.list_objects(Bucket = 'unverifiedphoto')['Contents']

                timeNow = datetime.now()
                threshold = 180

                canInsert = True

                for object in all_objects:
                    fileName = object['Key']
                    print (fileName)
                    if not fileName.startswith('photo'):
                        continue
                    original_time = datetime.strptime(fileName.split(".")[0][6:], "%m-%d-%Y-%H-%M-%S")
                    time_diff = (timeNow - original_time).total_seconds()
                    if (time_diff <= 180):
                        canInsert = False
                        break
                if not canInsert:
                    continue

                cv2.imwrite('/tmp/frame.jpg', frame)
                print("write frame to tmp")

                s3_client.upload_file(
                    '/tmp/frame.jpg',
                    unverified_bucket,
                    unverified_photo
                )
                cap.release()

                SESClient = boto3.client('ses')
                response = SESClient.send_email(
                    Source = 'hmh371@nyu.edu',
                    Destination = {
                        'ToAddresses':[
                            'hmh371@nyu.edu',
                        ]
                    },
                    Message = {
                        'Subject': {
                            'Data': 'Unkown visitor'
                        },
                        'Body': {
                            'Html': {
                                'Data': 'One unverified visitor is in front of your door:\n' + 'https://smartdoor30327.s3.amazonaws.com/addUser.html?link={unverified_photo}'.format(#@@@
                                    unverified_photo = unverified_photo
                                )
                            }
                        }
                    }
                )
                print('Image uploaded')
                return response

        return "no detected face"
    return "end"