const util = require('util');

const exec = util.promisify(require('child_process').exec);
const fs = require('fs-extra')
const os = require('os')
const ospath = require('path')
const shortid = require('shortid')
const walk = require('@nodelib/fs.walk')

const { HTTPError } = require('@/utils/error')

TASKS_DIR = ospath.join('/tmp', 'tasks')

exports.run = async (flags, image, command, inputFiles) => {
  // create a new task
  const taskID = shortid.generate()
  const taskPath = ospath.join(TASKS_DIR, taskID)
  fs.mkdirSync(taskPath, { recursive: true })

  // place input files
  let inputPaths = []
  for (const input of Object.values(inputFiles)) {
    inputPaths.push(ospath.join(taskPath, input.name))
    fs.copyFileSync(input.path, inputPaths[inputPaths.length-1])
  }

  // de-templatize flags
  flags = flags.replace('{{files}}', taskPath)

  // get stdout, stderr
  const fds = await exec(`docker run --rm ${flags} ${image} ${command}`)

  // delete input files
  for (const inputPath of inputPaths) {
    fs.removeSync(inputPath)
  }

  // get files
  const filenames = fs.readdirSync(taskPath)
  const files = {}
  for (const filename of filenames) {
    const filepath = ospath.join(taskPath, filename)
    const content = fs.readFileSync(filepath)
    files[filename] = content
  }
  return {fds, files}
}