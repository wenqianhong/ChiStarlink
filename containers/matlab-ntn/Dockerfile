FROM mathworks/matlab:r2025b@sha256:4b9d89af8499873d687372c79be062f14df609f3542ea7f322c0aedf81471314
USER root
WORKDIR /tmp
RUN wget -q https://www.mathworks.com/mpm/glnxa64/mpm -O /tmp/mpm \
    && chmod +x /tmp/mpm \
    && /tmp/mpm install --release=R2025b --destination=/opt/matlab/R2025b \
        --products 5G_Toolbox Satellite_Communications_Toolbox \
    && rm /tmp/mpm
USER matlab
WORKDIR /home/matlab
