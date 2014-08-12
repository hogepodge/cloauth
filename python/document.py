from lxml import etree
import sys
import os.path
import hashlib
import zipfile

class DocumentPrototype:
    def __init__(self):
        parser = etree.XMLParser(remove_blank_text=True)
        prototype_xml_filename=os.sep.join([os.path.dirname(__file__),'object.xml'])
        self.prototype = etree.parse(prototype_xml_filename, parser)
        for element in self.prototype.iter(): 
            element.tail = None
        self.document = etree.ElementTree(element=self.prototype.find("document"))
        #print self.document.write(sys.stdout)

    def set_primary(self):
        self._set_type('primary')

    def set_derived(self):
        self._set_type('derived')

    def _set_type(self, doctype):
        self.document.getroot().attrib['type'] = doctype

    def set_file(self, filename):
        filehash = self._md5(filename)

        file_elem = self.document.find('file')
        filename_elem = file_elem.find('filename')
        #filename_elem.text = filename
        filename_elem.text = os.path.basename(filename)

        hash_elem = file_elem.find('hash')
        hash_elem.text = filehash

    def set_file_stream(self, filename, stream):
        filehash = self._md5_stream(stream)
        file_elem = self.document.find('file')
        filename_elem = file_elem.find('filename')
        filename_elem.text = filename

        hash_elem = file_elem.find('hash')
        hash_elem.text = filehash

    ## def create_zipfile(self, directoryname):
    ##     """Walks the given directory, only zipping files one level deep (no subdirectories)"""
    ##     zfile_name = directoryname + ".zip"
    ##     zfile = zipfile.ZipFile(zfile_name, 'w', zipfile.ZIP_DEFLATED)
    ##     rootlen = len(directoryname) + 1
    ##     for base, dirs, files in os.walk(directoryname):
    ##         for f in files:
    ##             fn = os.path.join(directoryname, f)
    ##             zfile.write(fn, fn[rootlen:])
    ##     zfile.close()
    ##     self.set_file(zfile_name)


    def set_datasource(self, name, version):
        datasource = self.document.find('datasource')
        document_name = datasource.find('name')
        document_version = datasource.find('version')

        document_name.text = name
        document_version.text = version

    def add_datasource_meta(self, key, value):
        datasource = self.document.find('datasource')
        metadata = datasource.find('metadata')
        kv = etree.SubElement(metadata, 'meta', attrib={'key': key})
        kv.text = value

    def add_parentdata(self, key, objectid):
        parentdata = self.document.find('parentdata')
        parent = etree.SubElement(parentdata, 'parent', attrib={'key':key})
        parent.text = objectid

    def add_artifact(self, key, filename):
        """The assumption is that the filename points to a real file so the
        hash can be computed. Only the basename (no directory) of the filename
        is added to the manifest"""

        # compute the hash
        filehash = self._md5(filename)
        file_basename = os.path.basename(filename)

        # add the hash to the document
        artifacts = self.document.find('artifacts')
        artifact = etree.SubElement(artifacts, 'artifact', attrib={'key':key})
        art_filename = etree.SubElement(artifact, 'filename')
        art_filename.text = file_basename
        art_hash = etree.SubElement(artifact, 'hash', attrib={'algorithm':'md5'})
        art_hash.text = filehash

        # add to metadata, as artifacthash
        self.add_datasource_meta(key='artifacthash',value=filehash)
        

    def _md5(self, filename):
        f = file(filename, 'rb')
        return self._md5_stream(f)

    def _md5_stream(self, stream):
        blocksize = 65536
        buf = stream.read(blocksize)
        m = hashlib.md5()
        while len(buf) > 0:
            m.update(buf)
            buf = stream.read(blocksize)
        return m.hexdigest()

    def toxml(self):
        return etree.tostring(self.document, pretty_print=True)


#document = DocumentPrototype()
#document.set_datasource('test1', 'test2')
#document.add_datasource_meta('test3', 'test4')
#document.add_artifact('dicom', '112_0001438_252645/1.3.12.2.1107.5.2.7.20418.30000009010518365025000011332.dcm')
#document.create_zipfile('112_0001438_252645')
#document.add_parentdata('something', '12335')
#document.set_primary()
#print(etree.tostring(document.document, pretty_print=True))
