# python-google-api
A script uploading media to google photos cloud

1 Enable google photos API in your account https://developers.google.com/photos/library/guides/get-started
You need to choose that this is a Desktop app, otherwise you'll hit the Loopback IP address flow block.
You should have credentials.json file after this (rename from client_scret...json).

2 Install google api packages according to manual
https://developers.google.com/drive/api/v3/quickstart/python
pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib filelock

3 Put credentials.json in the folder with photos.py and run
python3 photos.py <some_picture>.jpg
Then you need to authorize with your google account.


