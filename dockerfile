FROM continuumio/miniconda3

# Set working directory
WORKDIR /app

# Copy your environment.yml file
COPY environment.yml .

# Create the environment (replace 'web-crawler' with your env name)
RUN conda env create -f environment.yml

# Make sure conda environment is activated
SHELL ["conda", "run", "-n", "web-crawler", "/bin/bash", "-c"]

# Copy your project files
COPY . .

# Install Playwright and Scrapy-Playwright with pip inside the environment
RUN conda run -n web-crawler pip install playwright scrapy-playwright && \
    conda run -n web-crawler playwright install --with-deps

# Expose FastAPI port
EXPOSE 8000

# Start FastAPI server
CMD ["conda", "run", "-n", "web-crawler", "uvicorn", "web-crawler:app", "--host", "0.0.0.0", "--port", "8000"]