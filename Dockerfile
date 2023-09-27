FROM python:3.10-alpine

RUN pip install requests

COPY ./delete-package-versions.py /delete-package-versions.py

ENTRYPOINT [ "/delete-package-versions.py" ]
