
# imports for Credentials class
import time 
import math
import random

# imports for OAuthClient
import requests.utils
import urlparse
import urllib
import requests
import binascii
import hmac
import hashlib


try: 
    from hashlib import sha1
    sha = sha1
except ImportError:
    # hashlib was added in Python 2.5
    import sha

class Credentials:
    def __init__(self, identifier, key, issue_time):
        self.identifier = identifier
        self.key = key
        self.algorithm = "hmac-sha1"
        self.issue_time = issue_time

    def generateNonce(self):
        t = (long(math.floor(time.time()) - self.issue_time))
        r1 = random.randint(1, 500000)
        r2 = random.randint(1, 500000)
        return "{time}:{rand1}{rand2}".format(time=t, rand1=r1, rand2=r2)

class OAuthClient:
    def __init__(self, credentials):
        self.credentials = credentials

    def compute_port(self, parsed):
        if (parsed.port == None):
            scheme = parsed.scheme
            if (scheme == "http"):
                return 80
            elif (scheme == "https"):
                return 443
        else:
            return parsed.port

    def fix_hostname(self, parsed):
        if (parsed.port != None):
            return parsed.netloc.lower().strip(":" + str(parsed.port))
        else:
            return parsed.netloc

    def fix_path(self, parsed):
        if (parsed.query != None and parsed.query != ""):
            return parsed.path + "?" + parsed.query
        else:
            return parsed.path

    def normalize(self, url, method, nonce, bodyhash):
        parsed = urlparse.urlparse(url)
        port = self.compute_port(parsed)
        return "{NONCE}\n{METHOD}\n{URL}\n{HOSTNAME}\n{PORT}\n{BODYHASH}\n{EXT}\n".format(
                NONCE     = nonce,
                METHOD    = method.upper(),
                URL       = self.fix_path(parsed),
                HOSTNAME  = self.fix_hostname(parsed),
                PORT      = port,
                BODYHASH  = bodyhash,
                EXT = "")

    def authorization(self, credentials, nonce, ext, mac, bodyhash=None):
        if bodyhash is not None:
            return "MAC id=\"{ID}\", nonce=\"{NONCE}\", bodyhash=\"{BODYHASH}\", ext=\"{EXT}\", mac=\"{MAC}\"".format(
                    ID       = credentials.identifier,
                    NONCE    = nonce,
                    BODYHASH = bodyhash,
                    EXT      = ext,
                    MAC      = mac)
        else:
            return "MAC id=\"{ID}\", nonce=\"{NONCE}\", ext=\"{EXT}\", mac=\"{MAC}\"".format(
                    ID       = credentials.identifier,
                    NONCE    = nonce,
                    EXT      = ext,
                    MAC      = mac)

    def generate_headers(self, url, method):
        nonce = self.credentials.generateNonce()
        bodyhash = "" # We're ignoring the body hash for now, should be fixed later
        normalization = self.normalize(url, method, nonce, bodyhash)
        ext = ""
        mac = binascii.b2a_base64(hmac.new(self.credentials.key,
                                           normalization,
                                           hashlib.sha1).digest()).rstrip('\n')
        authorization = self.authorization(self.credentials, nonce, ext, mac)
        return {'Authorization': authorization}

    def get(self, url, params=None, **kwargs):
        # Create a temporary url for oauth (matches what requests generates)
        headers = None
        if params is not None:
            newurl = self.prepare_url(url, params)
            headers = self.generate_headers(newurl, "GET")
        else:
            headers = self.generate_headers(url, "GET")

        # make the request
        r = requests.get(url, headers = headers, allow_redirects = False, verify = False, params=params, **kwargs)

        # if we encounter a redirect, rebuild the request for the new endpoint
        if r.status_code == 301:
            parsed = urlparse.urlparse(url)
            newurl = "{SCHEME}://{NETLOC}{PATH}".format(
                    SCHEME=parsed.scheme,
                    NETLOC=parsed.netloc,
                    PATH=r.headers["location"])
            headers = self.generate_headers(newurl, "GET")
            r = requests.get(newurl, headers = headers, allow_redirects = False, verify = False, params=params, **kwargs)

        return r

    def post(self, url, data=None, files=None, **kwargs):
        headers = self.generate_headers(url, "POST")
        return requests.post(url, headers=headers, data=data, files=files, **kwargs)

    def put(self, url, data=None, **kwargs):
        pass

    def delete(self, url):
        headers = self.generate_headers(url, "DELETE", **kwargs)
        return requests.delete(url, headers = headers, allow_redirects = False, verify = False, **kwargs)

    def head(self, url):
        headers = self.generate_headers(url, "HEAD", **kwargs)
        return requests.head(url, headers = headers, allow_redirects = False, verify = False, **kwargs)


    def prepare_url(self, url, params):
        scheme, netloc, path, _params, query, fragment = urlparse.urlparse(url)
        enc_params = self.encode_params(params)
        if enc_params:
            if query:
                query = '%s&%s' % (query, enc_params)
            else:
                query = enc_params

        url = requests.utils.requote_uri(urlparse.urlunparse(
            [scheme, netloc, path, _params, query, fragment]))
        return url

    def encode_params(self, data):
        if isinstance(data, (str, bytes)):
            return data
        elif hasattr(data, 'read'):
            return data
        elif hasattr(data, '__iter__'):
            result = []
            for k, vs in requests.utils.to_key_val_list(data):
                if isinstance(vs, basestring) or not hasattr(vs, '__iter__'):
                    vs = [vs]
                for v in vs:
                    if v is not None:
                        result.append(
                            (k.encode('utf-8') if isinstance(k, str) else k,
                             v.encode('utf-8') if isinstance(v, str) else v))
            return urllib.urlencode(result, doseq=True)
        else:
            return data
