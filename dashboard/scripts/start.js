const portForDevelopment = process.env.PORT_FOR_DEVELOPMENT || '3001';

process.env.PORT = portForDevelopment;

require('react-scripts/scripts/start');