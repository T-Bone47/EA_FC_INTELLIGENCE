// Preload in Node test workers that exercise the local API. IPC stays available to Vitest.
const net = require('node:net')
const dns = require('node:dns')
const udp = require('node:dgram')
const loopback = new Set(['127.0.0.1','::1','localhost'])
function requireLocal(host) {
  if (!loopback.has(host)) throw new Error('External networking is disabled for local QA.')
}
const connect = net.Socket.prototype.connect
net.Socket.prototype.connect = function (...args) {
  const value = Array.isArray(args[0]) ? args[0][0] : args[0]
  if (value && typeof value === 'object') {
    if (!value.path) requireLocal(value.host ?? 'localhost')
  } else if (typeof value === 'number' || /^\d+$/.test(String(value))) {
    requireLocal(typeof args[1] === 'string' ? args[1] : 'localhost')
  }
  return connect.apply(this,args)
}
for (const api of [dns, dns.promises]) {
  const lookup=api.lookup
  api.lookup=function(host,...rest){requireLocal(host);return lookup.call(this,host,...rest)}
}
udp.createSocket=()=>{throw new Error('UDP is disabled for local QA.')}
