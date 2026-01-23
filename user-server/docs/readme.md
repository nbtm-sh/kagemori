# kagemori user-server

## configuration

kagemori will look for a `config.yaml` file in the following directories.

- `./config.yaml`
- `${HOME}/.config/kagemori/config.yaml`

if the `KAGE_CONFIG` environment variable is set, this will override any of the above config locations.

## `config.yaml`

below is an example configuration file.

```yaml
auth_backend:
  - pam_auth

kagemori:
  prefix: "~/.config/kagemori"
  cookie: "kageauth"
  state_cache:
    use_state_cache: true
    state_cache_file: "~/.config/kagemori/state"
  logging:
    debug: true
    path: "~/.config/kagemori/logs"
  listen:
    socket: "/tmp/kagemori-%u/kagemori.sock"
    mask: "007"
    group: "kagemori"

nginx:
  listen:
    socket: "/tmp/kagemori-%u/nginx.sock"
    mask: "007"
    group: "kagemori"
  prefix: "~/.config/kagemori/nginx"
  path:
    config: "nginx.conf"
    tmp: "tmp"
    logs: "logs"
    pid: "nginx.pid"

ssl:
  expire_days: 1
  key_length: 4096
  identity:
    country: "JP"
    state: "93rd Ward"
    city: "Anima City"
    company: "Sylvasta Pharmaceuticals"
    company_section: "%u"

apps:
  - name: "hello-world"
    display_name: "hello-world"
    description: "hello world webapp"
    project_root: "~/.local/share/hello-world"
    domain: "hello.cluster.edu.au"
    control:
      start: "start.sh"
      stop: "stop.sh"
    environment:
      config_file: "KAGE_JOB_CONFIG"
      ssl_cert: "KAGE_SSL_CERT"
      ssl_key: "KAGE_SSL_KEY"
      domain_name: "KAGE_DOMAIN_NAME"
    queue:
      starting_poll_interval: 1 # Time to wait between checking the job state when waiting for it to start
      running_poll_interval: 10 # Time between checks of the job state
      await_config_timeout: 120 # Time to wait for the job to provide a valid config
```

## kagemori section

### `prefix`
the prefix path is the directory where kagemori will keep job configurations. by default, job configurations are kept in `~/.config/kagemori/.tmp`

### `cookie`
the name of the cookie that is used to authenticate the user. this should only be changed if it happens to overlap with the name of a cookie in the target webapp. this value must match what is configured on the manager server.

### `state_cache`
`use_state_cache`: if set to `true`, kagemori will note the state of apps in a cache file, so that the state can be recovered if the service is restarted. if this is set to false, kagemori will "forget" any running jobs when the server is restarted or reloaded.

`state_cache_file`: the path to the state cache file.

### `listen`
this defines the socket params that kagemori will listen on. kagemori user server is not capable of listening natively on a network socket, and you probably shouldn't try to make it do so.

`socket`: the path to the socket file that kagemori will bind to

`mask`: the file mask of the socket. this should be `007` or `000`. 

`group`: the group that should own the socket

