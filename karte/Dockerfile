ARG BUILD_FROM
FROM ${BUILD_FROM}

COPY requirements.txt /tmp/requirements.txt
# Pillow has no ready wheel for every architecture (armv7): then it is compiled, which needs zlib and libjpeg.
RUN apk add --no-cache zlib libjpeg-turbo \
    && apk add --no-cache --virtual .build-deps gcc musl-dev zlib-dev libjpeg-turbo-dev \
    && pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && apk del .build-deps

COPY app /app
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
