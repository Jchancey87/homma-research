module.exports = {
  apps: [
    {
      name: 'flask-backend',
      script: 'gunicorn',
      args: '-w 2 -b 0.0.0.0:5000 app:app',
      cwd: '/opt/trading-journal/backend',
      // Point at your venv interpreter
      interpreter: '/opt/trading-journal/backend/venv/bin/python',
      watch: false,
      autorestart: true,
      max_restarts: 10,
      env: {
        FLASK_ENV: 'production',
      },
      error_file: '/var/log/trading-journal/flask-err.log',
      out_file:   '/var/log/trading-journal/flask-out.log',
    },
    {
      name: 'nextjs-frontend',
      script: 'npm',
      args: 'start',
      cwd: '/opt/trading-journal/frontend',
      watch: false,
      autorestart: true,
      max_restarts: 10,
      env: {
        PORT: 3000,
        NODE_ENV: 'production',
        HOSTNAME: '127.0.0.1',           // bind to localhost; NPM proxies externally
        NEXT_PUBLIC_API_URL: 'http://192.168.0.202:5000',
      },
      error_file: '/var/log/trading-journal/nextjs-err.log',
      out_file:   '/var/log/trading-journal/nextjs-out.log',
    },
  ],
};
