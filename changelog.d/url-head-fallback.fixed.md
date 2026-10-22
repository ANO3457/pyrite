Retry source URL liveness checks with GET when a server refuses HEAD with 405 or 501; other HTTP errors remain broken sources and the response body is not downloaded.
