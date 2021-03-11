const cron = require('node-cron')
const fs = require('fs-extra')
const walk = require('@nodelib/fs.walk')

const WALK_SETTINGS = new walk.Settings({
  entryFilter: e => !e.name.startsWith('.') && e.dirent.isFile(),
  stats: true
})

// remove files not accessed in 1 day
const cleanup = () => {
  const expiryTime = new Date()
  expiryTime.setDate(expiryTime.getDate() - 1)

  const files = walk.walkSync('/tmp', WALK_SETTINGS)
  for (const file of files) {
    if (file.stats.atime < expiryTime) {
      fs.removeSync(file.path)
    }
  }
}

exports.init = () => {
  // run every hour
  cron.schedule('0 * * * *', cleanup)
}
