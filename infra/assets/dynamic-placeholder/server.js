/**
 * Placeholder web server for Lambda Web Adapter
 *
 * This is a minimal Express-like HTTP server that serves as a placeholder
 * until actual application code is deployed via the agent tool.
 *
 * Per AWS Lambda Web Adapter docs:
 * https://github.com/awslabs/aws-lambda-web-adapter
 */

const http = require('http');

const PORT = process.env.AWS_LWA_PORT || process.env.PORT || 3000;

const server = http.createServer((req, res) => {
  // Health check endpoint
  if (req.url === '/' || req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      message: 'UGC AI Demo - Dynamic Deployment Ready',
      info: 'Deploy your application code via the agent tool',
      timestamp: new Date().toISOString(),
    }));
    return;
  }

  // Default response for other paths
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({
    message: 'UGC AI Demo - Dynamic Deployment',
    path: req.url,
    method: req.method,
  }));
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});
