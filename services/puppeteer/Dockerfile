FROM ghcr.io/puppeteer/puppeteer:latest

# Set working directory
WORKDIR /app

# Copy app files
COPY . /app

USER root

# Fix permissions
RUN chown -R pptruser:pptruser /app

USER pptruser
# Install dependencies
RUN npm install

# Run the app
CMD ["node", "server.js"]
