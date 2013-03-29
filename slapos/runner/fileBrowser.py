# -*- coding: utf-8 -*-
# vim: set et sts=2:
# pylint: disable-msg=W0311,C0301,C0103,C0111

import datetime
import md5
import os
import re
import shutil
import urllib
import zipfile

import werkzeug
from slapos.runner.utils import realpath, tail, isText


class FileBrowser(object):
  """This class contain all bases function for file browser"""

  def __init__(self, config):
    self.config = config

  def _realdir(self, dir):
    realdir = realpath(self.config, urllib.unquote(dir))
    if not realdir:
      raise NameError('Could not load directory %s: Permission denied' % dir)
    return realdir

  def listDirs(self, dir, all=False):
    """List elements of directory 'dir' taken"""
    html = 'var gsdirs = [], gsfiles = [];'

    dir = urllib.unquote(dir)
    # 'dir' is used below. XXX should not shadow a builtin name
    realdir = realpath(self.config, dir)
    if not realdir:
      raise NameError('Could not load directory %s: Permission denied' % dir)

    ldir = sorted(os.listdir(realdir), key=str.lower)
    for f in ldir:
      if f.startswith('.') and not all: #do not display this file/folder
        continue
      ff = os.path.join(dir, f)
      realfile = os.path.join(realdir, f)
      mdate = datetime.datetime.fromtimestamp(os.path.getmtime(realfile)
                    ).strftime("%Y-%d-%m %I:%M")
      md5sum = md5.md5(realfile).hexdigest()
      if not os.path.isdir(realfile):
        size = os.path.getsize(realfile)
        regex = re.compile("(^.*)\.(.*)", re.VERBOSE)
        ext = regex.sub(r'\2', f)
        if ext == f:
          ext = "unknow"
        else:
          ext = str.lower(ext)
        html += 'gsfiles.push(new gsItem("1", "' + f + '", "' + \
                  ff + '", "' + str(size) + '", "' + md5sum + \
                  '", "' + ext + '", "' + mdate + '"));'
      else:
        html += 'gsdirs.push(new gsItem("2", "' + f + '", "' + \
                  ff + '", "0", "' + md5sum + '", "dir", "' + mdate + '"));'
    return html


  def makeDirectory(self, dir, filename):
    """Create a directory"""
    realdir = self._realdir(dir)
    folder = os.path.join(realdir, filename)
    if not os.path.exists(folder):
      os.mkdir(folder, 0744)
      return '{result: \'1\'}'
    else:
      return '{result: \'0\'}'


  def makeFile(self, dir, filename):
    """Create a file in a directory dir taken"""
    realdir = self._realdir(dir)
    fout = os.path.join(realdir, filename)
    if not os.path.exists(fout):
      open(fout, 'w')
      return 'var responce = {result: \'1\'}'
    else:
      return '{result: \'0\'}'

  def deleteItem(self, dir, files):
    """Delete a list of files or directories"""
    realdir = self._realdir(dir)
    lfiles = urllib.unquote(files).split(',,,')
    try:
      for file in lfiles:
        file = os.path.join(realdir, file)
        if not os.path.exists(file):
          continue #silent skip file....
        details = file.split('/')
        last = details[-1]
        if last and last.startswith('.'):
          continue #cannot delete this file/directory, to prevent security
        if os.path.isdir(file):
          shutil.rmtree(file)
        else:
          os.unlink(file)
    except Exception as e:
      return str(e)
    return '{result: \'1\'}'

  def copyItem(self, dir, files, del_source=False):
    """Copy a list of files or directory to dir"""
    realdir = self._realdir(dir)
    lfiles = urllib.unquote(files).split(',,,')
    try:
      for file in lfiles:
        realfile = realpath(self.config, file)
        if not realfile:
          raise NameError('Could not load file or directory %s: Permission denied' % file)
        #prepare destination file
        details = realfile.split('/')
        dest = os.path.join(realdir, details[-1])
        if os.path.exists(dest):
          raise NameError('NOT ALLOWED OPERATION : File or directory already exist')
        if os.path.isdir(realfile):
          shutil.copytree(realfile, dest)
          if del_source:
            shutil.rmtree(realfile)
        else:
          shutil.copy(realfile, dest)
          if del_source:
            os.unlink(realfile)
    except Exception as e:
      return str(e)
    return '{result: \'1\'}'

  def rename(self, dir, filename, newfilename):
    """Rename file or directory to dir/filename"""
    realdir = self._realdir(dir)
    realfile = realpath(self.config, urllib.unquote(filename))
    if not realfile:
      raise NameError('Could not load directory %s: Permission denied' % filename)
    tofile = os.path.join(realdir, newfilename)
    if not os.path.exists(tofile):
      os.rename(realfile, tofile)
      return '{result: \'1\'}'
    raise NameError('NOT ALLOWED OPERATION : File or directory already exist')

  def copyAsFile(self, dir, filename, newfilename):
    """Copy file or directory to dir/filename"""
    realdir = self._realdir(dir)
    fromfile = os.path.join(realdir, filename)
    tofile = os.path.join(realdir, newfilename)
    if not os.path.exists(fromfile):
      raise NameError('NOT ALLOWED OPERATION : File or directory not exist')
    if not os.path.exists(tofile):
      shutil.copy(fromfile, tofile)
      return '{result: \'1\'}'
    raise NameError('NOT ALLOWED OPERATION : File or directory already exist')

  def uploadFile(self, dir, files):
    """Upload a list of file in directory dir"""
    realdir = self._realdir(dir)
    for file in files:
      if files[file]:
        filename = werkzeug.secure_filename(files[file].filename)
        if not os.path.exists(os.path.join(dir, filename)):
          files[file].save(os.path.join(realdir, filename))
    return '{result: \'1\'}'

  def downloadFile(self, dir, filename):
    """Download file dir/filename"""
    realdir = self._realdir(dir)
    file = os.path.join(realdir, urllib.unquote(filename))
    if not os.path.exists(file):
      raise NameError('NOT ALLOWED OPERATION : File or directory does not exist %s'
                      % os.path.join(dir, filename))
    return file

  def zipFile(self, dir, filename, newfilename):
    """Add filename to archive as newfilename"""
    realdir = self._realdir(dir)
    tozip = os.path.join(realdir, newfilename)
    fromzip = os.path.join(realdir, filename)
    if not os.path.exists(fromzip):
      raise NameError('NOT ALLOWED OPERATION : File or directory not exist')
    if not os.path.exists(tozip):
      zip = zipfile.ZipFile(tozip, 'w', zipfile.ZIP_DEFLATED)
      if os.path.isdir(fromzip):
        rootlen = len(fromzip) + 1
        for base, _, files in os.walk(fromzip):
          for filename in files:
            fn = os.path.join(base, filename).encode("utf-8")
            zip.write(fn, fn[rootlen:])       # XXX can fail if 'fromzip' contains multibyte characters
      else:
        zip.write(fromzip)
      zip.close()
      return '{result: \'1\'}'
    raise NameError('NOT ALLOWED OPERATION : File or directory already exist')

  def unzipFile(self, dir, filename, newfilename):
    """Extract a zipped archive"""
    realdir = self._realdir(dir)
    target = os.path.join(realdir, newfilename)
    archive = os.path.join(realdir, filename)
    if not os.path.exists(archive):
      raise NameError('NOT ALLOWED OPERATION : File or directory not exist')
    if not os.path.exists(target):
      zip = zipfile.ZipFile(archive)
      #member = zip.namelist()
      zip.extractall(target)
      #if len(member) > 1:
      #  zip.extractall(target)
      #else:
      #  zip.extract(member[0], newfilename)
      return '{result: \'1\'}'
    raise NameError('NOT ALLOWED OPERATION : File or directory already exist')

  def readFile(self, dir, filename, truncate=False):
    """Read file dir/filename and return content"""
    realfile = realpath(self.config, os.path.join(urllib.unquote(dir),
                        urllib.unquote(filename)))
    if not realfile:
      raise NameError('Could not load directory %s: Permission denied' % dir)
    if not isText(realfile):
      return "FILE ERROR: Cannot display binary file, please open a text file only!"
    if not truncate:
      return open(realfile, 'r').read()
    else:
      return tail(open(realfile, 'r'), 0)