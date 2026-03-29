/**
 * Uppy Companion server configuration
 * 
 * This file configures the Companion server for Uppy file uploads
 * from remote sources like Dropbox, Google Drive, OneDrive, and Google Photos.
 * 
 * Author: Vadim Kalinin
 * Email: vadimakalin@gmail.com
 */

const companion = require('@uppy/companion');

// Get configuration from environment variables
const {
  COMPANION_PORT = 3020,
  COMPANION_DOMAIN = 'localhost:3020',
  COMPANION_PROTOCOL = 'http',
  COMPANION_SECRET,
  COMPANION_ALLOWED_HOSTS,
  
  // Google Drive & Photos
  COMPANION_GOOGLE_KEY,
  COMPANION_GOOGLE_SECRET,
  
  // Dropbox
  COMPANION_DROPBOX_KEY,
  COMPANION_DROPBOX_SECRET,
  
  // OneDrive
  COMPANION_ONEDRIVE_KEY,
  COMPANION_ONEDRIVE_SECRET,
  
  // File upload settings
  COMPANION_DATADIR = '/tmp/companion',
} = process.env;

// Validate required configuration
if (!COMPANION_SECRET) {
  console.error('ERROR: COMPANION_SECRET environment variable is required');
  console.error('Generate one with: node -e "console.log(require(\'crypto\').randomBytes(64).toString(\'hex\'))"');
  process.exit(1);
}

// Parse allowed hosts
const corsOrigins = COMPANION_ALLOWED_HOSTS 
  ? COMPANION_ALLOWED_HOSTS.split(',').map(host => host.trim())
  : true; // Allow all origins if not specified

// Build provider options
const providerOptions = {};

if (COMPANION_GOOGLE_KEY && COMPANION_GOOGLE_SECRET) {
  providerOptions.drive = {
    key: COMPANION_GOOGLE_KEY,
    secret: COMPANION_GOOGLE_SECRET,
  };
}

if (COMPANION_DROPBOX_KEY && COMPANION_DROPBOX_SECRET) {
  providerOptions.dropbox = {
    key: COMPANION_DROPBOX_KEY,
    secret: COMPANION_DROPBOX_SECRET,
  };
}

if (COMPANION_ONEDRIVE_KEY && COMPANION_ONEDRIVE_SECRET) {
  providerOptions.onedrive = {
    key: COMPANION_ONEDRIVE_KEY,
    secret: COMPANION_ONEDRIVE_SECRET,
  };
}

// Build companion URL
const companionUrl = `${COMPANION_PROTOCOL}://${COMPANION_DOMAIN}`;

console.log(`🚀 Starting Uppy Companion server...`);
console.log(`📡 Companion URL: ${companionUrl}`);
console.log(`🔌 Port: ${COMPANION_PORT}`);

// Configure Companion
const options = {
  providerOptions,
  server: {
    host: COMPANION_DOMAIN,
    protocol: COMPANION_PROTOCOL,
  },
  filePath: COMPANION_DATADIR,
  secret: COMPANION_SECRET,
  corsOrigins: corsOrigins,
};

// Log enabled providers
const enabledProviders = Object.keys(providerOptions);
if (enabledProviders.length > 0) {
  console.log(`✅ Enabled providers: ${enabledProviders.join(', ')}`);
} else {
  console.warn('⚠️  No cloud providers configured. Add credentials to enable Dropbox, Google Drive, OneDrive, etc.');
}

// Create Companion app
const { app: companionApp } = companion.app(options);

// Add a simple root route for health check
companionApp.get('/', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: 'Uppy Companion',
    url: companionUrl,
    providers: Object.keys(providerOptions),
    message: 'Companion server is running'
  });
});

// Start server
const server = companionApp.listen(COMPANION_PORT, () => {
  console.log(`✅ Uppy Companion server is running on port ${COMPANION_PORT}`);
  console.log(`🌐 Access at: ${companionUrl}`);
});

// Enable WebSocket support for real-time updates
companion.socket(server);

// Handle errors
server.on('error', (error) => {
  console.error('❌ Companion server error:', error);
});

process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down Companion server...');
  server.close(() => {
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down Companion server...');
  server.close(() => {
    process.exit(0);
  });
});
