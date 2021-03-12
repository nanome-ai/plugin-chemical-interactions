const util = require('util');

const exec = util.promisify(require('child_process').exec);
const fs = require('fs-extra')
const os = require('os')
const ospath = require('path')
const shortid = require('shortid')
const walk = require('@nodelib/fs.walk')

const { HTTPError } = require('@/utils/error')

TASKS_DIR = ospath.join('/tmp', 'tasks')

$local = { image: ''}

exports.init = async dockerfile => {
  // only initialize once
  if (!$local.image) {
    dockerfilePath = ospath.join(TASKS_DIR, 'Dockerfile')
    fs.writeFileSync(dockerfilePath, dockerfile)
    const image = 'dockerfile'

    let { _, stderr: buildErr } = await exec(`docker build -t ${image} -f ${dockerfilePath} .`)
    if (buildErr) {
      throw new HTTPError(400, 'Could not build docker image')
    }

    $local.image = image
  }
}

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
  const fds = await exec(`docker run ${flags} ${image} ${command}`).catch(e=>{throw new HTTPError(500, 'Could not run command:', e)})

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