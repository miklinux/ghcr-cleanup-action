FROM python:3.10-alpine

ENV \
  TOKEN=$INPUT_TOKEN \
  PACKAGE_OWNER=$INPUT_PACKAGE_OWNER \
  PACKAGE_NAME=$INPUT_PACKAGE_NAME \
  KEEP_VERSIONS=$INPUT_KEEP_VERSIONS \
  DELETE_ORPHANS=$INPUT_DELETE_ORPHANS \
  DRY_RUN=$INPUT_DRY_RUN

RUN pip install requests

COPY ./delete-package-versions.py /delete-package-versions.py

ENTRYPOINT [ "python3", "/delete-package-versions.py" ]
