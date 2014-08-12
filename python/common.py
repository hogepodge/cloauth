import dicomobject as do
import brainkobject as bko
import lfmobject

import os
import poauth
from lxml import etree
import hashlib

verbose=True
def lout(string):
    if verbose==True :
        print string,

def load_credential_token_from_xml(fname):
    """fname should be xml file of type produced by server by dowloading token"""
    try :
        token_xml=etree.parse(open(fname))
        identifier= token_xml.findall('mac-key-identifier')[0].text
        key = token_xml.findall('mac-key')[0].text
        issue_time=token_xml.findall('issue-time')[0].text
        server=token_xml.findall('hostname')[0].text
        token=poauth.Credentials(identifier=identifier,
                                 key=key,
                                 issue_time=int(issue_time) )
    except Exception as e :
        print 'Could not load credential token from file ' +fname
        raise(e)
    
    return (server,token)
    
def checkexistence(server, token, query):
    client = poauth.OAuthClient(token)
    response = client.get(query)
    if response.status_code != 200:
        raise Exception("Bad server response. Expected 200. Got %s" % (response.status_code))

    documentlist = None 
    try:
        documentlist = etree.fromstring(response.text)
    except:
        # demanding strict correctness with XML? Silliness
        documentlist = etree.fromstring(response.text[38:])

    if documentlist.tag != "objects":
        raise "Expected a list of objects from the server."

    return documentlist

def determine_file_type(pathname) :
    # file could be an .nii file, or a .gps file, or unknown
    if os.path.isfile(pathname) :
        if pathname.endswith('.nii') or pathname.endswith('.nii.gz') :
            return 'nii'
        elif pathname.endswith('.sfp') or pathname.endswith('.gps') :
            return 'gps'
        elif pathname.endswith('.Parameters.txt') :
            return 'bkparam'
        elif pathname.endswith('.hdr') :
            D=lfmobject.parselfmheader(pathname)
            if 'LFM format' in D :
                return 'lfm'
            else :
                raise Exception('.hdr file ' +pathname +' does not look like an lfm header')
        else :
            pass
    if os.path.isdir(pathname) :
        if do.isvaliddicom(pathname):
            return 'dicomdir'

    return 'unknown'

# code for hashing / checking in "raw" files where little else is known
def checkrawfileexistence(server,token,hash) :
    querystring = ''.join([server, "/object.xml?key=hash&value=", hash])
    documentlist = checkexistence(server,token,querystring)
    if len(documentlist) == 0:
        return None
    else: 
        return documentlist[0]

def rawfilehash(pathname) :
    blocksize = 65536
    fid=open(pathname)
    buf = fid.read(blocksize)
    m = hashlib.md5()
    while len(buf) > 0:
        m.update(buf)
        buf = fid.read(blocksize)
    return m.hexdigest()


def get_id_from_parsed_xml(obj) :
    """ obj should be None, or lxml.etree._Element """
    obj_id = None
    if not obj is None :
        for child in obj :
            if child.tag == 'id' :
                obj_id=child.text
    return obj_id

def get_parents_from_parsed_xml(obj) :
    try :
        parentdata_element=obj.findall('parentdata')[0]
        parent_ids=[x.text for x in parentdata_element.findall('parent')]
        return parent_ids
    except IndexError :
        return []
    
def get_database_xml_from_path(server,token,pathname) :
    # is it a valid dicom directory?
    # is it a braink parameters.txt file?
    # is it an unknown file?

    # if it is a directory, assume it is a dicom directory
    # if it is a file, check if it is a brainK parameters.txt file
    # otherwise, for now assume it is a raw file

    if not os.path.exists(pathname) :
        object_xml=None
    
    if os.path.isdir(pathname) :
        if do.isvaliddicom(pathname) :
            df=do.getfirstdicomfile(pathname)
            object_xml=do.checkdicomexistence(server,token,df.SeriesInstanceUID)
        
    if os.path.isfile(pathname) :
        if pathname.endswith('.Parameters.txt') :
            bkstub=pathname.replace('.Parameters.txt','')
            bkhash=bko.brainkhash(bkstub)
            object_xml=bko.checkbrainkexistence(server,token,bkhash)
        else :
            # 'raw' file case
            rawhash=rawfilehash(pathname)
            object_xml=checkrawfileexistence(server,token,rawhash)
            #raise Exception('raw file case not implemented yet')
        
    return object_xml

    ## try :
    ##     object_id=object_xml.findall('id')[0].text
    ## except :
    ##     object_id=None
    ## return object_id

    
def parse_xml_from_server(xmlstring) :
    """ xml string from server may need 38 characters removed from
    beginning : this function encapsulates this hack in a single place
    so it need not be spread throughout source"""
    try :
        parsed_xml=etree.fromstring(xmlstring)
    except Exception as e :
        #print(e.__repr__())
        # magic number : 38 (removes instance encoding string)
        parsed_xml=etree.fromstring(xmlstring[38:])
    # check if it is xml : if it is html, then server gave something invalid
    # todo : better check than below for being passed html
    if len(parsed_xml.findall('body'))==1 and len(parsed_xml.findall('head'))==1:
        raise Exception('html found instead of xml')
    if get_id_from_parsed_xml(parsed_xml) is None :
        raise Exception('no id returned from server xml : likely there was bad input given to server')
    return parsed_xml
