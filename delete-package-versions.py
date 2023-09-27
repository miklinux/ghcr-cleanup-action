#!/usr/bin/env python3

import os
import sys
import requests
import base64
import json
import urllib.parse

# GitHub PAT used for performing the API calls
TOKEN = os.environ.get("INPUT_TOKEN")
# GitHub organization / ghcr.io repo owner
PACKAGE_OWNER = os.environ.get("INPUT_PACKAGE-OWNER")
# Name of the package, must include relative path
PACKAGE_NAME = os.environ.get("INPUT_PACKAGE-NAME")
# Number of versions to keep for the package
KEEP_VERSIONS = int(os.environ.get("INPUT_KEEP-VERSIONS", 5))
# Delete versions which are not referenced by any tag
DELETE_ORPHANS = (os.environ.get("INPUT_DELETE-ORPHANS", 'false') == 'true')
# Don't perform DELETE API calls
DRY_RUN = (os.environ.get("INPUT_DRY-RUN", 'false') == 'true')

# API response caches
all_versions = []
all_versions_tagged = []

# Encode a string to base64
def base64_encode(value):
  return base64.b64encode(str(value).encode()).decode()

# Urlencode a string
def urlencode(value):
  return urllib.parse.quote(str(value), safe='')

# Perform an API call to the ghcr.io registry requesting the
# manifest for the given SHA digest to find out all versions
# which are related to the multi-arch manifest.
def get_children_manifests(sha):
  response = requests.get(
    f"https://ghcr.io/v2/{PACKAGE_OWNER}/{PACKAGE_NAME}/manifests/{sha}",
    headers={
      "Accept": ','.join([
        'application/vnd.docker.distribution.manifest.v2+json',
        'application/vnd.oci.image.index.v1+json'
       ]),
      "Authorization": f"Bearer {base64_encode(TOKEN)}"
    }
  )

  if response.status_code == 404:
    print(f"WARNING: No children packages found for SHA {sha}")
    return []
  elif response.status_code != 200:
    print(f"Failed to fetch manifest with HTTP status {response.status_code}")
    sys.exit(1)

  result = []
  for manifest in response.json()['manifests']:
    for version in get_all_versions():
      if version['name'] == manifest['digest']:
        child_version = version
        # Add the platform name as an extra information
        child_version['platform'] = f"%s/%s" % (
          manifest['platform']['os'],
          manifest['platform']['architecture']
        )
        result.append(child_version)
        break

  return result

# Retrieve all versions for a package and stores the
# result into the cache for later retrieval
def get_all_versions():
  global all_versions

  if len(all_versions) == 0:
    package_name = urlencode(PACKAGE_NAME)
    response = requests.get(
      f"https://api.github.com/orgs/{PACKAGE_OWNER}/packages/container/{package_name}/versions",
      headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}"
      }
    )

    if response.status_code == 404:
      return []
    elif response.status_code != 200:
      print(f"Failed to fetch package versions with HTTP status {response.status_code}")
      sys.exit(1)

    # Store the value into cache
    all_versions = response.json()

  return all_versions

# Parses the response from get_all_versions() to retrieve
# all tagged versions together with their children manifests.
# Stores the information into cache for later retrieval.
def get_all_versions_tagged():
  global all_versions_tagged

  if len(all_versions_tagged) == 0:
    for version in get_all_versions():
      tags = version['metadata']['container']['tags']
      if len(tags) > 0:
        tagged_version = version
        tagged_version['children'] = get_children_manifests( version['name'] )
        all_versions_tagged.append(tagged_version)

  # Store the value into cache
  return all_versions_tagged

# Slice the get_all_versions_tagged() result to return a list
# containing the versions to keep and the versions to delete,
# based on the KEEP_VERSIONS parameter
def get_versions_to_delete():
  versions = get_all_versions_tagged()
  return [
    versions[ 0:KEEP_VERSIONS ], # versions to keep
    versions[ KEEP_VERSIONS: ]   # versions to delete
  ]

# Extract and compares all version ids from get_all_version()
# and get_all_versions_tagged() to retrieve all versions which
# do not have any associated tag.
def get_orphan_versions():
  diff_version_ids = list(
    set(extract_ids(get_all_versions())) -
    set(extract_ids(get_all_versions_tagged()))
  )
  result = []
  for diff_version_id in diff_version_ids:
    for version in get_all_versions():
      if diff_version_id == version['id']:
        result.append(version)
        break

  return result

# Extract all 'id' fields from the given data and return
# them as a list
def extract_ids(data):
  ids = []
  if isinstance(data, dict):
    if "id" in data:
      ids.append(data["id"])
    for key, value in data.items():
      ids.extend(extract_ids(value))
  elif isinstance(data, list):
    for item in data:
      ids.extend(extract_ids(item))

  return sorted(ids)

# Shortcut for getting a specific tag for a package
def get_version_tag(version, index = -1):
  return version['metadata']['container']['tags'][index]

# Perform the API call to delete a version
def delete_version(version_id):
  # Make to function return true if DRY_RUN
  if DRY_RUN:
    return True

  package_name = urlencode(PACKAGE_NAME)
  response = requests.delete(
    f"https://api.github.com/orgs/{PACKAGE_OWNER}/packages/container/{package_name}/versions/{version_id}",
    headers={
      "Accept": "application/vnd.github+json",
      "Authorization": f"Bearer {TOKEN}"
    }
  )

  if response.status_code == 204:
    return True
  else:
    print(f"!! Failed to delete version {version_id} (HTTP status {response.status_code})")
    return False

# Main script logic
def main():
  # Parameters validation
  if not PACKAGE_OWNER or not PACKAGE_NAME or not TOKEN:
    print("Please set at least PACKAGE_OWNER, PACKAGE_NAME and TOKEN environment variables.")
    sys.exit(1)

  i=0
  if DRY_RUN:
    print("WARNING: Running in DRY-RUN mode")

  print(f"Performing API calls for package {PACKAGE_OWNER}/{PACKAGE_NAME} ...")

  # Loop over the get_version_to_delete() dict and perform the deletion
  keep_versions, delete_versions = get_versions_to_delete()

  # Counters
  num_keep_versions = len(keep_versions)
  num_delete_versions = len(delete_versions)

  # Process package versions to keep
  if num_keep_versions > 0:
    print(f"The following {num_keep_versions} package version(s) will be kept:")
    for keep_version in keep_versions:
      keep_version_tag = get_version_tag(keep_version)
      print( f"  %-10s : %s (%s)" % (
        keep_version['id'],
        keep_version['name'],
        keep_version_tag,
      ))
  elif num_keep_versions == 0 and num_delete_versions > 0:
    print("ALL existing package versions will be deleted ...")
  else:
    print("There are no package versions to keep")

  # Process package versions to delete
  if num_delete_versions > 0:
    print(f"Deleting {num_delete_versions} package version(s) ...")
    for parent_version in delete_versions:
      parent_version_tag = get_version_tag(parent_version)
      # Delete root version
      print( f"  %-10s : %s (%s, multi-arch)" % (
        parent_version['id'],
        parent_version['name'],
        parent_version_tag,
      ))
      delete_version( parent_version['id'] )
      # Delete children versions if any
      for child_version in parent_version['children']:
        print( f"  %-10s : %s (%s, %s)" % (
          child_version['id'],
          child_version['name'],
          parent_version_tag,
          child_version['platform'],
        ))
        delete_version( child_version['id'] )
  else:
    print("There are no package versions to delete")

  # Process orphan package versions to delete
  if DELETE_ORPHANS:
    orphan_versions = get_orphan_versions()
    num_orphan_versions = len(orphan_versions)
    if num_orphan_versions > 0:
      print(f"Deleting {num_orphan_versions} orphan container manifests(s) ...")
      for orphan_version in orphan_versions:
        if delete_version( orphan_version['id'] ):
          print(f"  %-10s : %s" % (
            orphan_version['id'],
            orphan_version['name']
          ))
    else:
       print("There are no orphan package versions to delete")

# Main
if __name__ == "__main__":
  main()
