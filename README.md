# ghcr.io Cleanup - GitHub Action

This action deletes versions of multi-arch container packages stored on [GitHub Packages](https://github.com/features/packages).

Requires Python 3 installed on the action runner

# Usage

```yaml
- uses: miklinux/ghcr-cleanup-action@v1
  with:
    # GitHub PAT used to perform the API calls
    # Must have packages:read and packages:delete permissions
    token: ghp_xxx
    # Owner or organization to which the package belongs
    package-owner: my-awesome-org
    # Name of the package
    package-name: my-awesome-package
    # Number of versions to keep
    min-versions-to-keep: 5
    # Delete untagged versions not belonging to any multi-arch manifest
    delete-orphans: false
    # Dry-run mode: won't perform DELETE API requests.
    dry-run: false
```
