const express = require('express')
const router = express.Router()
const task = require('@/services/task')
const asyncWrap = require('@/utils/async-wrap')

router.post(
  '/init',
  asyncWrap(async (req, res) => {
    let { dockerfile } = req.fields
    const data = await task.init(dockerfile)
    return res.success({data})
  })
)

router.post(
  '/',
  asyncWrap(async (req, res) => {
    let files = req.files
    let { flags, image, command } = req.fields
    const data = await task.run(flags, image, command, files)
    return res.success({data})
  })
)

module.exports = router
