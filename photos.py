#!/usr/bin/env python3
from __future__ import print_function
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import requests
import sys
import time
import os
import filelock
from datetime import datetime

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly',
          'https://www.googleapis.com/auth/photoslibrary.sharing']

def get_file_list_in_directory_by_extension(mypath, ext):
    return [os.path.join(mypath, f) for f in os.listdir(mypath) if os.path.isfile(os.path.join(mypath, f)) and f.endswith(ext)]


def move_one_file_to_cloud(creds, albumId, file_to_upload_full_path):
    print('Uploading {}'.format(file_to_upload_full_path))
    file_to_upload_name = os.path.basename(file_to_upload_full_path)
    file_to_upload_mtime = os.path.getmtime(file_to_upload_full_path)
    file_to_upload_timestamp = datetime.utcfromtimestamp(file_to_upload_mtime).strftime('%Y-%m-%d %H:%M:%S')
    headers = {
    'Content-Type': "application/octet-stream",
    'X-Goog-Upload-File-Name': file_to_upload_name,
    'X-Goog-Upload-Protocol': "raw",
    'Authorization': "Bearer " + creds.token,
    }
     
    data = open(file_to_upload_full_path, 'rb').read()
    response = requests.post('https://photoslibrary.googleapis.com/v1/uploads', headers=headers, data=data)
    response.raise_for_status()
    image_token = response.text
    headers = {
        'Content-Type': "application/json",
        'Authorization': "Bearer " + creds.token,
        }
    reqbody = {
          'albumId': albumId,
          'newMediaItems': [
            {
              'description': file_to_upload_timestamp,
              'simpleMediaItem': {
                'uploadToken': image_token
              }
            }
          ]
        }

    response = requests.post('https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate', headers=headers, json=reqbody)
    uploadErr = response.raise_for_status()
    if response.ok:
        print('Successfully uploaded {}'.format(file_to_upload_full_path))
    elif uploadErr:
        print('Failed to upload {} error: {}'.format(file_to_upload_full_path, uploadErr))
    if response.ok and os.path.exists(file_to_upload_full_path):
        os.remove(file_to_upload_full_path)

def auth():
    script_workdir = os.path.dirname(os.path.realpath(__file__))
    credentials_token_path = os.path.join(script_workdir, 'token.pickle')
    credentials_json_path = os.path.join(script_workdir, 'credentials.json') 
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(credentials_token_path):
        with open(credentials_token_path, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        print('No OAuth tokens found, starting auth');
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_json_path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(credentials_token_path, 'wb') as token:
            pickle.dump(creds, token)
    return creds

def main(creds):
    script_workdir = os.path.dirname(os.path.realpath(__file__))
    service = build('photoslibrary', 'v1', credentials=creds, static_discovery=False)
    # Call the Photo v1 API
    results = service.albums().list(
        pageSize=10, fields="nextPageToken,albums(id,title)").execute()
    albumName = 'helloworld'
    if len(sys.argv) > 2:
        albumName = sys.argv[2]
    albumId = None
    items = results.get('albums', [])
    if not items:
        print('No albums found.')
    else:
        print('Albums:')
        for item in items:
            print('{0} ({1})'.format(item['title'].encode('utf8'), item['id']))
            if item['title'] == albumName:
                albumId = item['id']
    
    if albumId == None:
        print('Album not found, creating a new one')
        response_create_album = service.albums().create(body={'album':{'title':albumName, 'isWriteable': 'true'}}).execute()
        albumId = response_create_album['id']
        headers = {
        'Content-Type': "application/json",
        'Authorization': "Bearer " + creds.token,
        }
        reqbody = {
        "sharedAlbumOptions": {
        "isCollaborative": "true",
        "isCommentable": "true"
        }
        }
        response = requests.post('https://photoslibrary.googleapis.com/v1/albums/{}:share'.format(response_create_album['id']), headers=headers, json=reqbody)
        response.raise_for_status()

    print('Uploading to album with id ' + albumId)
        
    if len(sys.argv) > 1:
        """
        wait a minute if the file hasn't been created yet
        """
        file_to_upload_full_path = sys.argv[1]
        if not os.path.isfile(file_to_upload_full_path):
            print('File not found, waiting for file')
        start = time.time()
        while time.time() - start < 60:
            if os.path.isfile(file_to_upload_full_path):
                break
            else:
                time.sleep(1)
        file_to_upload_dir_path = os.path.dirname(os.path.realpath(file_to_upload_full_path))
        file_to_upload_mtime = os.path.getmtime(file_to_upload_full_path)
        move_one_file_to_cloud(creds, albumId, file_to_upload_full_path)
    else:
        # check for mp4 files in the script directory only
        file_to_upload_dir_path = script_workdir
        # and push them ignoring timestamps
        file_to_upload_mtime = float('Inf')

    # check for other videos
    other_videos_to_upload = get_file_list_in_directory_by_extension(file_to_upload_dir_path, '.mp4')
    if len(other_videos_to_upload) > 0:
        for vid in other_videos_to_upload:
            # exclude newer files that may be in progress
            if file_to_upload_mtime > os.path.getmtime(vid):
                move_one_file_to_cloud(creds, albumId, vid)


if __name__ == '__main__':
    cred = None
    file_lock_path = "//tmp//photos.py.lock"
    lock = filelock.FileLock(file_lock_path)
    try:
        with lock.acquire(timeout=1):
            cred = auth()
            lock.release()
        main(cred)
    except filelock.Timeout:
        print('{} is locked. Is another instance running?'.format(file_lock_path))
        pass
