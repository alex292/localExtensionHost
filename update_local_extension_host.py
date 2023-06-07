import argparse
import json
import sys
import os
import subprocess
import binascii
import string
import struct
import shutil
import xml.etree.ElementTree
from pkg_resources import parse_version
from xml.dom import minidom


# https://stackoverflow.com/questions/16993486/how-to-programmatically-calculate-chrome-extension-id
def decode(proto, data):
  index = 0
  length = len(data)
  msg = dict()
  while index < length:
    item = 128
    key = 0
    left = 0
    while item & 128:
      item = data[index]
      index += 1
      value = (item & 127) << left
      key += value
      left += 7
    field = key >> 3
    wire = key & 7
    if wire == 0:
      item = 128
      num = 0
      left = 0
      while item & 128:
        item = data[index]
        index += 1
        value = (item & 127) << left
        num += value
        left += 7
      continue
    elif wire == 1:
      index += 8
      continue
    elif wire == 2:
      item = 128
      _length = 0
      left = 0
      while item & 128:
        item = data[index]
        index += 1
        value = (item & 127) << left
        _length += value
        left += 7
      last = index
      index += _length
      item = data[last:index]
      if field not in proto:
        continue
      msg[proto[field]] = item
      continue
    elif wire == 5:
      index += 4
      continue
    raise ValueError('invalid wire type: {wire}'.format(wire=wire))
  return msg


# https://stackoverflow.com/questions/16993486/how-to-programmatically-calculate-chrome-extension-id
def get_extension_id(crx_file):
  with open(crx_file, 'rb') as f:
    f.read(8)
    # 'Cr24\0\0\0\3'
    data = f.read(struct.unpack('<I', f.read(4))[0])
  crx3 = decode({10000: "signed_header_data"}, [ord(d) for d in data])
  signed_header = decode({1: "crx_id"}, crx3['signed_header_data'])
  return string.translate(
      binascii.hexlify(bytearray(signed_header['crx_id'])),
      string.maketrans('0123456789abcdef', string.ascii_lowercase[:16]))


def increase_version_number(version):
  parts = version.split('.')
  parts[-1] = str(int(parts[-1]) + 1)
  return '.'.join(parts)


def main():
  parser = argparse.ArgumentParser(
    usage='update_local_extension_host <path_to_extension> [--extension_host_url <extension_host_url>] [--chrome_path <chrome_path>]')
  parser.add_argument(
      'path_to_extension',
      type=str,
      help='path to the extension (required)')
  parser.add_argument(
      '--extension_host_url',
      type=str, default='http://127.0.0.1:8888',
      help='optional extension host url')
  parser.add_argument(
      '--chrome_path',
      type=str, default='google-chrome',
      help='path to the chrome version')

  args = parser.parse_args()

  path_to_extension = args.path_to_extension
  extension_host_url = args.extension_host_url
  chrome_path = args.chrome_path

  dir_path = os.path.dirname(os.path.realpath(__file__))
  host_dir = dir_path + '/host'
  pem_dir = dir_path + '/PEMs'

  # Check if dir for extension exists and actually is an extension
  if path_to_extension.endswith('/'):
    path_to_extension = path_to_extension[:-1]
  if not os.path.isdir(path_to_extension):
    print('Could not find given path:' + path_to_extension)
    return
  if not os.path.isfile(path_to_extension + '/manifest.json'):
    print(
        'Could not locate manifest at :' + path_to_extension + '/manifest.json')
    return

  extension_name = os.path.split(path_to_extension)[1]
  has_pem_file = os.path.isfile(pem_dir + '/' + extension_name + '.pem')

  # Read existing extension IDs
  ids_file = open(pem_dir + '/ids.json', 'r+')
  ids_json = json.load(ids_file)
  extension_id = None
  if has_pem_file and extension_name in ids_json:
    extension_id = ids_json[extension_name]

  # Read version from manifest.json
  manifest_file = open(path_to_extension + '/manifest.json', 'r')
  manifest_json = json.load(manifest_file)
  manifest_file.close()
  manifest_version = manifest_json['version']

  # Read update_manifest.xml
  update_manifest_file_path = host_dir + '/update_manifest.xml'
  update_manifest_xml = minidom.parse(update_manifest_file_path)
  gupdate = update_manifest_xml.getElementsByTagName('gupdate')[0]

  # Read version from update_manifest.xml (if available)
  update_manifest_version = '-1'
  update_manifest_entry = None
  version = manifest_json['version']
  if extension_id:
    for app in gupdate.getElementsByTagName('app'):
      if app.attributes['appid'].value == extension_id:
        update_manifest_entry = app
    if update_manifest_entry:
      update_manifest_version = update_manifest_entry.getElementsByTagName(
          'updatecheck')[0].getAttribute('version')
      if update_manifest_version != -1 and parse_version(
          update_manifest_version) >= parse_version(manifest_json['version']):
        version = increase_version_number(update_manifest_version)

  # Move original manifest file
  shutil.move(path_to_extension + '/manifest.json',
              path_to_extension + '/manifest_orig.json')

  # Save temporary manifest (with updated version and update_url)
  manifest_json['version'] = version
  manifest_json['update_url'] = extension_host_url + '/update_manifest.xml'
  manifest_temp_file = open(path_to_extension + '/manifest.json', 'w')
  json.dump(manifest_json, manifest_temp_file, indent=2)
  manifest_temp_file.close()

  # Pack extension
  if has_pem_file:
    subprocess.call([
        chrome_path, '--pack-extension=' + path_to_extension,
        '--pack-extension-key=' + pem_dir + '/' + extension_name + '.pem'
    ])
  else:
    subprocess.call([chrome_path, '--pack-extension=' + path_to_extension])
    # Move .pem file
    shutil.move(path_to_extension + '.pem',
                pem_dir + '/' + extension_name + '.pem')

  # Move .crx file
  shutil.move(path_to_extension + '.crx',
              host_dir + '/' + extension_name + '.crx')

  # Read extension ID and store it
  if not extension_id:
    extension_id = get_extension_id(host_dir + '/' + extension_name + '.crx')
    ids_json[extension_name] = extension_id
    ids_file.seek(0)
    json.dump(ids_json, ids_file, indent=2)

  # Update update_manifest.xml
  if update_manifest_entry:
    updatecheck = update_manifest_entry.getElementsByTagName('updatecheck')[0]
    updatecheck.setAttribute('version', version)
    updatecheck.setAttribute('codebase',
                             extension_host_url + '/' + extension_name + '.crx')
  else:
    update_manifest_entry = update_manifest_xml.createElement('app')
    update_manifest_entry.setAttribute('appid', extension_id)
    updatecheck = update_manifest_xml.createElement('updatecheck')
    updatecheck.setAttribute('codebase',
                             extension_host_url + '/' + extension_name + '.crx')
    updatecheck.setAttribute('version', version)
    update_manifest_entry.appendChild(updatecheck)
    gupdate.appendChild(update_manifest_entry)
  update_manifest_file = open(update_manifest_file_path, 'wb')
  update_manifest_file.write(update_manifest_xml.toxml('UTF-8'))
  update_manifest_file.close()

  # Restore original manifest version
  shutil.move(path_to_extension + '/manifest_orig.json',
              path_to_extension + '/manifest.json')

  # Debug infos
  print('Extension name: ' + extension_name)
  print('Extension ID: ' + extension_id)
  print('Manifest version: ' + manifest_version)
  print('Previously served version: ' + update_manifest_version)
  print('Newly served version: ' + version)


if __name__ == "__main__":
  main()
