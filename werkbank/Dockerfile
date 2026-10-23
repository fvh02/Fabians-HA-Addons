# FreeCAD (headless) comes from conda-forge – Ubuntu 24.04 no longer ships it, and conda-forge has
# the same version for amd64 and arm64.
FROM mambaorg/micromamba:2.0.5

USER root
ENV PYTHONUNBUFFERED=1 QT_QPA_PLATFORM=offscreen PATH=/opt/conda/bin:$PATH

RUN micromamba install -y -n base -c conda-forge "freecad=1.1.3" "python=3.12" pillow numpy pip \
    && micromamba clean -a -y \
    && freecadcmd --version

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /app
COPY run.sh /run.sh
RUN chmod a+rx /run.sh && chmod -R a+rX /app
ENTRYPOINT []
CMD [ "/run.sh" ]
