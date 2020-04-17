import boto3
import json


# import cv2      # *** Before upload to lambda function, I have to install the dependencies on the local path

def detectFaces(bucket, photo):
    client = boto3.client('rekognition')

    response = client.detect_faces(
        Image={
            'S3Object': {
                'Bucket': bucket,
                'Name': photo,
            }
        }
    )
    return response


def createCollection(collection_id):
    client = boto3.client('rekognition')

    # Create a collection
    response = client.create_collection(CollectionId=collection_id)
    print("Collection {} is created!".format(collection_id))
    return response['CollectionArn']


def indexFaces(bucket, photo_key, collection_id):
    s3 = boto3.client('rekognition')

    response = s3.index_faces(
        CollectionId=collection_id,
        Image={
            'S3Object': {
                'Bucket': bucket,
                'Name': photo_key,
            }
        },
        ExternalImageId=photo_key,
        QualityFilter="AUTO",
        DetectionAttributes=['ALL']
    )

    print("Face indexed into the collection!")
    print(response)


def checkCollectionExists(collection_id):
    client = boto3.client('rekognition')

    response = client.list_collections()

    collections = response['CollectionIds']

    print(response)
    if not collection_id in collections:
        print("No such collection exists! Create one!")
        return False
    else:
        print("Such collection exists")
        return True


def describeCollection(collection_id):
    client = boto3.client('rekognition')

    response = client.describe_collection(
        CollectionId=collection_id
    )
    return response

def listCollections():
    client = boto3.client('rekognition')

    response = client.list_collections(

    )

    return response


def lambda_handler(event, context):
    # TODO implement

    """
    Add the face image to the collection called "faces-collection".
    """
    photo = event['pic']
    bucket = "visitors-face"
    collection_id = "faces-collection"

    indexed_faces = add_faces_to_collections




    # *** Have to replace event object with test cases after this



    if not checkCollectionExists(collection_id):
        createCollection(collection_id)

    indexFaces(bucket, face_key, collection_id)

    print(describeCollection(collection_id))


    """
    Add 
    """


