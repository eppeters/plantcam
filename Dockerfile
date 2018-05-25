FROM python:3.6.5-alpine3.7
RUN mkdir /app
WORKDIR /app
RUN apk --no-cache --update-cache add gcc freetype-dev libpng-dev openblas-dev build-base
RUN apk add jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY timelapse.py /app/
ENTRYPOINT ["python", "timelapse.py"]
