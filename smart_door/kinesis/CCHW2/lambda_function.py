import boto3
import json
import base64


# import cv2      # *** Before upload to lambda function, I have to install the dependencies on the local path


def getDataEndPoint(stream_arn, api_name):
    kv = boto3.client("kinesisvideo")

    response = kv.get_data_endpoint(
        StreamARN=stream_arn,
        APIName=api_name
    )

    return response


def getMedia(stream_arn, end_point):
    kvm = boto3.client("kinesis-video-media", endpoint_url=end_point)

    response = kvm.get_media(
        StreamARN=stream_arn,
        StartSelector={
            "StartSelectorType": "NOW"
        }
    )

    return response


def lambda_handler(event, context):
    # TODO implement

    """
    read video from Kinesis Video Streams as event object ??? Not find it from event
    """
    stream_arn = "arn:aws:kinesisvideo:us-east-1:971614317796:stream/smart-door/1586919175374"
    api_name = "GET_MEDIA"

    end_point_data = getDataEndPoint(stream_arn, api_name)

    end_point = end_point_data['DataEndpoint']

    media_response = getMedia(stream_arn, end_point)  # Without endpoint, the request would be denied

    payload = media_response['Payload']

    with open('/tmp/recoginition.mkv', 'wb') as f:
        stream_body = payload.read()
        f.write(stream_body)
    f.close()






















