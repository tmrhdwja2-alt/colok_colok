FROM mambaorg/micromamba:2.0.5

USER root
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN micromamba install -y -n base -c conda-forge -c bioconda \
      python=3.11 amrfinderplus=4.0.23 pip \
    && micromamba run -n base pip install --no-cache-dir -r /app/requirements.txt \
    && micromamba clean --all --yes

COPY . /app
RUN mkdir -p /app/uploads /app/amrfinder-data \
    && chown -R $MAMBA_USER:$MAMBA_USER /app

USER $MAMBA_USER
ENV PATH=/opt/conda/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    AMRFINDER_DB=/app/amrfinder-data

RUN amrfinder_update --database /app/amrfinder-data

EXPOSE 10000
CMD ["/bin/sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]

