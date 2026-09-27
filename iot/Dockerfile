# A small, non-root image for the software-only IoT device simulator.
FROM python:3.12.5-slim
WORKDIR /device
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY device_simulator.py ./
RUN useradd --system --uid 10001 simulator && chown -R simulator:simulator /device
USER 10001
ENTRYPOINT ["python", "device_simulator.py"]
