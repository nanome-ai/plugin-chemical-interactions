class HTTPError extends Error {
  constructor(status, message) {
    super(message)
    this.name = this.constructor.name
    this.status = status
  }
}

HTTPError.UNAUTHORIZED = new HTTPError(401, 'Unauthorized')
HTTPError.FORBIDDEN = new HTTPError(403, 'Forbidden')
HTTPError.NOT_FOUND = new HTTPError(404, 'Not Found')

exports.HTTPError = HTTPError
