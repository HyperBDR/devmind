import morphdom from 'morphdom'

export function updateWorkspaceDom(host, html, prepare = () => {}) {
  const target = host.cloneNode(false)
  target.innerHTML = html
  prepare(target)
  morphdom(host, target, { childrenOnly: true })
  prepare(host)
}
