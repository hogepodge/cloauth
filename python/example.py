import poauth

# credentials to test against http://prodigal.nic.uoregon.edu:3604
mac_key_identifier = "7020b02d-5240-41d8-981d-ce2faf0115a8"
mac_key            = "08712e33-e62b-4a39-85e7-e2bb64dad2cb"
issue_time         = 1357856519246

# second set of credentials to test against, https://neuroapp.nic.uoregon.edu:8181
#mac_key_identifier = "3b597f98-1000-4cee-b3e9-b54348be1a27"
#mac_key            = "237a0bf0-a860-4a42-baf4-48fbc034a43c"
#issue_time         = 1360880371128

credentials = poauth.Credentials(mac_key_identifier, mac_key, issue_time)
client = poauth.OAuthClient(credentials)

#response = client.get("https://neuroapp.nic.uoregon.edu:8181/object.xml")
#print response # the respnse should be a 400 error, although that response itself is a bug

#response = client.get("http://prodigal.nic.uoregon.edu:3604/object.xml?key=description&value=t1")
#print response.text

#response = client.get("http://prodigal.nic.uoregon.edu:3604/object.xml",
#        params={"key": "description", "value": "t1"})
#print response.text

#response = client.get("http://prodigal.nic.uoregon.edu:3604/object/511bd0563a26c2b90b087c81/file")
#        params={"key": "description", "value": "t1"})
#print response.text

# note that for the object endpoint the xml is sent as a data object, while 
# the binary file payload is sent as a file. It's an important distinction,
# and one that needs to be observed
response = client.post("http://prodigal.nic.uoregon.edu:3604/object",
        data={"object": open("example-derived-preload.xml").read()},
        files={"file": open("example.zip", "rb")})

# the response is exactly the same one returned by the requests library
# http://docs.python-requests.org/en/latest/

print response.text
