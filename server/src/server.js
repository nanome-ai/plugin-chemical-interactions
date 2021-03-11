require('module-alias/register')

const http = require('http')
const app = require('./app')
const cron = require('./services/cron')

http.createServer(app).listen(80)
cron.init()