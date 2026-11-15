import {
  Clock,
  Config,
  Console,
  DateTime,
  Effect,
  FileSystem,
  Option,
  Path,
  Random,
  Schema,
} from "effect";
import { HttpClient, HttpClientRequest } from "effect/http";
import { Argument, Command, Flag } from "effect/cli";
import { ChildProcess, ChildProcessSpawner } from "effect/process";

const apiBase = "https://api.verda.com/v1";

class GpuFailed extends Schema.TaggedError<GpuFailed>()("GpuFailed", {
  message: Schema.String,
}) {}

const Credentials = Schema.Struct({
  client_id: Schema.String,
  client_secret: Schema.String,
});

const Token = Schema.Struct({ access_token: Schema.String });

const Tag = Schema.Struct({
  key: Schema.String,
  value: Schema.optional(Schema.NullOr(Schema.String)),
});

const Instance = Schema.Struct({
  id: Schema.String,
  hostname: Schema.String,
  status: Schema.String,
  instance_type: Schema.String,
  location: Schema.String,
  ip: Schema.NullOr(Schema.String),
  price_per_hour: Schema.Finite,
  created_at: Schema.String,
  os_volume_id: Schema.optional(Schema.NullOr(Schema.String)),
  volume_ids: Schema.optional(Schema.NullOr(Schema.Array(Schema.String))),
  tags: Schema.optional(Schema.NullOr(Schema.Array(Tag))),
});

type Instance = typeof Instance.Type;

const InstanceType = Schema.Struct({
  instance_type: Schema.String,
  gpu_memory: Schema.Struct({ size_in_gigabytes: Schema.Finite }),
  price_per_hour: Schema.FiniteFromString,
  spot_price: Schema.FiniteFromString,
});

const Availability = Schema.Struct({
  location_code: Schema.String,
  availabilities: Schema.Array(Schema.String),
});

const SshKey = Schema.Struct({ id: Schema.String, name: Schema.String, key: Schema.String });

const Balance = Schema.Struct({ amount: Schema.Finite, currency: Schema.String });

const credentialsPath = Effect.fn("gpu.credentialsPath")(function* credentialsPath() {
  const path = yield* Path.Path;

  return path.resolve(import.meta.dirname, "../../../infra/verda/credentials.json");
});

const readCredentials = Effect.fn("gpu.readCredentials")(function* readCredentials() {
  const fs = yield* FileSystem.FileSystem;
  const file = yield* credentialsPath();

  const text = yield* fs
    .readFileString(file)
    .pipe(
      Effect.mapError(
        () =>
          new GpuFailed({ message: `Cannot read ${file}. Fix: run from a full repo checkout.` }),
      ),
    );

  return yield* Schema.decodeEffect(Schema.fromJsonString(Credentials))(text).pipe(
    Effect.mapError(
      () => new GpuFailed({ message: `${file} must hold client_id and client_secret.` }),
    ),
  );
});

type Method = "DELETE" | "GET" | "POST" | "PUT";

const request = Effect.fn("gpu.request")(function* request(
  method: Method,
  url: string,
  token: string,
  body: string | undefined,
) {
  const client = yield* HttpClient.HttpClient;
  const base = HttpClientRequest.make(method)(url).pipe(HttpClientRequest.acceptJson);
  const withAuth = token === "" ? base : base.pipe(HttpClientRequest.bearerToken(token));

  const withBody =
    body === undefined
      ? withAuth
      : withAuth.pipe(HttpClientRequest.bodyText(body, "application/json"));

  const response = yield* client
    .execute(withBody)
    .pipe(Effect.mapError(() => new GpuFailed({ message: `${method} ${url}: network error` })));

  const text = yield* response.text.pipe(
    Effect.mapError(() => new GpuFailed({ message: `${method} ${url}: cannot read the response` })),
  );

  if (response.status >= 300) {
    return yield* new GpuFailed({
      message: `${method} ${url} returned ${response.status}: ${text}`,
    });
  }

  return text;
});

const accessToken = Effect.fn("gpu.accessToken")(function* accessToken() {
  const credentials = yield* readCredentials();

  const text = yield* request(
    "POST",
    `${apiBase}/oauth2/token`,
    "",
    JSON.stringify({ grant_type: "client_credentials", ...credentials }),
  );

  const token = yield* Schema.decodeEffect(Schema.fromJsonString(Token))(text).pipe(
    Effect.mapError(() => new GpuFailed({ message: "The token response has no access_token." })),
  );

  return token.access_token;
});

const call = Effect.fn("gpu.call")(function* call<A>(
  schema: Schema.Decoder<A>,
  method: Method,
  route: string,
  body: string | undefined,
) {
  const token = yield* accessToken();
  const text = yield* request(method, `${apiBase}${route}`, token, body);

  return yield* Schema.decodeEffect(Schema.fromJsonString(schema))(text).pipe(
    Effect.mapError(
      (error) =>
        new GpuFailed({ message: `${method} ${route}: unexpected response. ${error.message}` }),
    ),
  );
});

const send = Effect.fn("gpu.send")(function* send(method: Method, route: string, body: string) {
  const token = yield* accessToken();

  return yield* request(method, `${apiBase}${route}`, token, body);
});

const create = Effect.fn("gpu.create")(function* create(route: string, body: string) {
  const text = yield* send("POST", route, body);
  const id = text.trim().replaceAll('"', "");

  if (id === "") {
    return yield* new GpuFailed({ message: `POST ${route} returned no ID.` });
  }

  return id;
});

const localUser = Effect.fn("gpu.localUser")(function* localUser() {
  const user = yield* Config.String("USER").pipe(Config.withDefault("team"));

  const clean = user.toLowerCase().replaceAll(/[^a-z0-9]/gu, "");

  return clean === "" ? "team" : clean;
});

const tagValue = (instance: Instance, key: string) =>
  instance.tags?.find((tag) => tag.key === key)?.value ?? "";

const hoursLeft = (instance: Instance, now: number) => {
  const expires = Date.parse(tagValue(instance, "expires"));

  return Number.isNaN(expires) ? "?" : `${((expires - now) / 3_600_000).toFixed(1)}h`;
};

const imageFor = (instanceType: string) => {
  if (instanceType.startsWith("CPU")) {
    return "24.04.base";
  }

  return instanceType.includes("V100") ? "24.04.cuda12.9-v100.docker" : "24.04.cuda13.4.docker";
};

export const expiryScript = (
  hostname: string,
  expiresAt: string,
  clientId: string,
  clientSecret: string,
) => {
  const calendar = expiresAt.slice(0, 19).replace("T", " ");

  return `#!/bin/bash
set -u
cat > /usr/local/sbin/verda-expire <<'SCRIPT'
#!/bin/bash
set -eu
token=$(curl -fsS -X POST ${apiBase}/oauth2/token -H 'Content-Type: application/json' \\
  -d '{"grant_type":"client_credentials","client_id":"${clientId}","client_secret":"${clientSecret}"}' \\
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
body=$(curl -fsS ${apiBase}/instances -H "Authorization: Bearer $token" | python3 -c '
import sys, json
for i in json.load(sys.stdin):
    if i["hostname"] == "${hostname}":
        volumes = [v for v in [i.get("os_volume_id")] + (i.get("volume_ids") or []) if v]
        print(json.dumps({"action": "delete", "id": i["id"], "volume_ids": sorted(set(volumes)), "delete_permanently": True}))
        break
')
curl -fsS -X PUT ${apiBase}/instances -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -d "$body"
SCRIPT
chmod 700 /usr/local/sbin/verda-expire
cat > /etc/systemd/system/verda-expire.service <<'UNIT'
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/verda-expire
Restart=on-failure
RestartSec=60
UNIT
cat > /etc/systemd/system/verda-expire.timer <<'UNIT'
[Timer]
OnCalendar=${calendar} UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now verda-expire.timer
`;
};

const teamKeyPath = Effect.fn("gpu.teamKeyPath")(function* teamKeyPath() {
  const fs = yield* FileSystem.FileSystem;
  const path = yield* Path.Path;
  const file = path.resolve(import.meta.dirname, "../../../infra/verda/team_ed25519");

  yield* fs
    .chmod(file, 0o600)
    .pipe(
      Effect.mapError(() => new GpuFailed({ message: `Cannot find the team SSH key ${file}.` })),
    );

  return file;
});

const sshOptions = Effect.fn("gpu.sshOptions")(function* sshOptions() {
  const teamKey = yield* teamKeyPath();

  return [
    "-i",
    teamKey,
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "LogLevel=ERROR",
    "-o",
    "ServerAliveInterval=30",
  ];
});

const registerKey = Effect.fn("gpu.registerKey")(function* registerKey(
  publicKey: string,
  name: string,
  existing: readonly (typeof SshKey.Type)[],
) {
  const keyBody = publicKey.split(/\s+/u)[1] ?? publicKey;

  if (existing.some((key) => key.key.includes(keyBody))) {
    return;
  }

  yield* create("/ssh-keys", JSON.stringify({ key: publicKey, name }));
  yield* Console.log(`added SSH key ${name} to the team account`);
});

const ensureSshKey = Effect.fn("gpu.ensureSshKey")(function* ensureSshKey(keyFile: string) {
  const fs = yield* FileSystem.FileSystem;
  const path = yield* Path.Path;
  const home = yield* Config.String("HOME").pipe(Config.withDefault(""));
  const teamKey = yield* teamKeyPath();
  const existing = yield* call(Schema.Array(SshKey), "GET", "/ssh-keys", undefined);

  yield* registerKey(
    (yield* fs.readFileString(`${teamKey}.pub`)).trim(),
    "junction-2026-team",
    existing,
  );

  const candidates =
    keyFile === ""
      ? ["id_ed25519.pub", "id_rsa.pub"].map((name) => path.join(home, ".ssh", name))
      : [keyFile];

  const found = yield* Effect.findFirst(candidates, (candidate) => fs.exists(candidate));

  if (Option.isSome(found)) {
    const publicKey = (yield* fs.readFileString(found.value)).trim();
    const user = yield* localUser();

    yield* registerKey(
      publicKey,
      `${user}-${publicKey.split(/\s+/u)[2] ?? "key"}`.slice(0, 60),
      existing,
    );
  }

  return yield* call(Schema.Array(SshKey), "GET", "/ssh-keys", undefined);
});

const findInstance = Effect.fn("gpu.findInstance")(function* findInstance(nameOrId: string) {
  const instances = yield* call(Schema.Array(Instance), "GET", "/instances", undefined);

  const match = instances.find(
    (instance) => instance.hostname === nameOrId || instance.id === nameOrId,
  );

  if (match === undefined) {
    return yield* new GpuFailed({ message: `No VM named ${nameOrId}. Run \`pnpm j gpu ls\`.` });
  }

  return match;
});

const types = Command.make(
  "types",
  {},
  Effect.fn("gpu.types")(function* types() {
    const catalog = yield* call(Schema.Array(InstanceType), "GET", "/instance-types", undefined);

    const availability = yield* call(
      Schema.Array(Availability),
      "GET",
      "/instance-availability",
      undefined,
    );

    yield* Console.log("type                   GPU RAM   $/h     spot $/h  free now in");

    for (const entry of catalog.toSorted((a, b) => a.price_per_hour - b.price_per_hour)) {
      const locations = availability
        .filter((location) => location.availabilities.includes(entry.instance_type))
        .map((location) => location.location_code);

      if (locations.length > 0) {
        yield* Console.log(
          `${entry.instance_type.padEnd(22)} ${`${entry.gpu_memory.size_in_gigabytes}GB`.padEnd(9)} ${entry.price_per_hour.toFixed(2).padEnd(7)} ${entry.spot_price.toFixed(2).padEnd(9)} ${locations.join(", ")}`,
        );
      }
    }

    yield* Console.log("Next: pnpm j gpu up <type> --hours 3");
  }),
).pipe(Command.withDescription("List the GPU types you can start now, with their prices"));

const list = Command.make(
  "ls",
  {},
  Effect.fn("gpu.ls")(function* list() {
    const instances = yield* call(Schema.Array(Instance), "GET", "/instances", undefined);
    const balance = yield* call(Balance, "GET", "/balance", undefined);
    const now = yield* Clock.currentTimeMillis;

    yield* Console.log(`balance: ${balance.amount.toFixed(2)} ${balance.currency}`);

    if (instances.length === 0) {
      yield* Console.log("no VMs. Next: pnpm j gpu types");
    }

    for (const instance of instances) {
      yield* Console.log(
        `${instance.hostname.padEnd(24)} ${instance.status.padEnd(13)} ${instance.instance_type.padEnd(18)} $${instance.price_per_hour.toFixed(2)}/h  owner ${tagValue(instance, "owner") || "?"}  deletes in ${hoursLeft(instance, now)}  ${instance.ip === null ? "" : `ssh root@${instance.ip}`}`,
      );
    }
  }),
).pipe(Command.withDescription("List the team's VMs, their cost and the account balance"));

const up = Command.make(
  "up",
  {
    disk: Flag.Int("disk").pipe(Flag.withDescription("OS disk size in GB"), Flag.withDefault(100)),
    hours: Flag.Int("hours").pipe(
      Flag.withDescription("The VM deletes itself after this many hours (1 to 24)"),
      Flag.withDefault(4),
    ),
    image: Flag.String("image").pipe(
      Flag.withDescription("Image type from the Verda API. Default: Ubuntu 24.04 + CUDA + Docker"),
      Flag.withDefault(""),
    ),
    key: Flag.String("key").pipe(
      Flag.withDescription("Your SSH public key file. Default: ~/.ssh/id_ed25519.pub"),
      Flag.withDefault(""),
    ),
    location: Flag.String("location").pipe(
      Flag.withDescription("Location code, such as FIN-01. Default: the first with free capacity"),
      Flag.withDefault(""),
    ),
    spot: Flag.Boolean("spot").pipe(
      Flag.withDescription("Half price, but Verda can stop it at any time"),
      Flag.withDefault(false),
    ),
    type: Argument.String("type").pipe(
      Argument.withDescription("Instance type from `pnpm j gpu types`, such as 1A100.22V"),
    ),
  },
  Effect.fn("gpu.up")(function* up({ disk, hours, image, key, location, spot, type }) {
    if (!Number.isInteger(hours) || hours < 1 || hours > 24) {
      return yield* new GpuFailed({ message: "--hours must be 1 to 24." });
    }

    const availability = yield* call(
      Schema.Array(Availability),
      "GET",
      "/instance-availability",
      undefined,
    );

    const free = availability
      .filter((entry) => entry.availabilities.includes(type))
      .map((entry) => entry.location_code);

    const target = location === "" ? free[0] : location;

    if (target === undefined || !free.includes(target)) {
      return yield* new GpuFailed({
        message: `${type} has no free capacity${location === "" ? "" : ` in ${location}`}. Run \`pnpm j gpu types\`.`,
      });
    }

    const keys = yield* ensureSshKey(key);
    const credentials = yield* readCredentials();
    const user = yield* localUser();
    const suffix = (yield* Random.nextIntBetween(0x10_00, 0xff_ff)).toString(16);
    const hostname = `${user}-${type.split(".")[0]?.toLowerCase() ?? "gpu"}-${suffix}`;
    const expiresAt = DateTime.formatIso(DateTime.add(yield* DateTime.now, { hours }));

    const scriptId = yield* create(
      "/scripts",
      JSON.stringify({
        name: `expire-${hostname}`,
        script: expiryScript(hostname, expiresAt, credentials.client_id, credentials.client_secret),
      }),
    );

    const id = yield* create(
      "/instances",
      JSON.stringify({
        contract: spot ? "SPOT" : "PAY_AS_YOU_GO",
        description: `pnpm j gpu up by ${user}`,
        hostname,
        image: image === "" ? imageFor(type) : image,
        instance_type: type,
        is_spot: spot,
        location_code: target,
        os_volume: spot
          ? { name: `${hostname}-os`, on_spot_discontinue: "delete_permanently", size: disk }
          : { name: `${hostname}-os`, size: disk },
        ssh_key_ids: keys.map((entry) => entry.id),
        startup_script_id: scriptId,
        tags: [
          { key: "owner", value: user },
          { key: "expires", value: expiresAt },
          { key: "j-gpu" },
        ],
      }),
    ).pipe(
      Effect.tapError(() =>
        send("DELETE", "/scripts", JSON.stringify({ scripts: [scriptId] })).pipe(Effect.ignore),
      ),
    );

    yield* Console.log(
      `ordered ${hostname} (${type} in ${target}). It deletes itself at ${expiresAt}.`,
    );

    let instance = yield* findInstance(id);
    let lastStatus = "";

    for (
      let attempt = 0;
      attempt < 120 && (instance.status !== "running" || instance.ip === null);
      attempt += 1
    ) {
      if (
        ["error", "no_capacity", "installation_failed", "discontinued"].includes(instance.status)
      ) {
        return yield* new GpuFailed({
          message: `${hostname} is ${instance.status}. Fix: run \`pnpm j gpu down ${hostname}\`, then try another type or location.`,
        });
      }

      if (instance.status !== lastStatus) {
        yield* Console.log(`  ${instance.status}`);
        lastStatus = instance.status;
      }

      yield* Effect.sleep("5 seconds");
      instance = yield* findInstance(id);
    }

    yield* send("DELETE", "/scripts", JSON.stringify({ scripts: [scriptId] })).pipe(Effect.ignore);

    if (instance.status !== "running" || instance.ip === null) {
      return yield* new GpuFailed({
        message: `${hostname} is still ${instance.status} after 10 minutes. Check \`pnpm j gpu ls\`. It still costs money until \`pnpm j gpu down ${hostname}\`.`,
      });
    }

    yield* Console.log(`running: ssh root@${instance.ip}   (or: pnpm j gpu ssh ${hostname})`);
    yield* Console.log(`Delete it when you are done: pnpm j gpu down ${hostname}`);
  }),
).pipe(Command.withDescription("Start a GPU VM that deletes itself after --hours"));

const down = Command.make(
  "down",
  {
    name: Argument.String("name").pipe(
      Argument.withDescription("VM name or ID from `pnpm j gpu ls`"),
    ),
  },
  Effect.fn("gpu.down")(function* down({ name }) {
    const instance = yield* findInstance(name);

    const volumes = [...new Set([instance.os_volume_id, ...(instance.volume_ids ?? [])])].filter(
      (volume): volume is string => volume !== null && volume !== undefined,
    );

    yield* send(
      "PUT",
      "/instances",
      JSON.stringify({
        action: "delete",
        delete_permanently: true,
        id: instance.id,
        volume_ids: volumes,
      }),
    );

    yield* Console.log(
      `deleting ${instance.hostname} and its ${volumes.length} volume(s). Billing stops.`,
    );
  }),
).pipe(Command.withDescription("Delete a VM and its disks, so it stops costing money"));

const remoteDir = (localDir: string) =>
  `/root/work/${localDir.split("/").findLast((part) => part !== "") ?? "job"}`;

const runningIp = Effect.fn("gpu.runningIp")(function* runningIp(name: string) {
  const instance = yield* findInstance(name);

  if (instance.ip === null || instance.status !== "running") {
    return yield* new GpuFailed({
      message: `${instance.hostname} is ${instance.status} with no IP yet. Wait and retry.`,
    });
  }

  return instance.ip;
});

const runLocal = Effect.fn("gpu.runLocal")(function* runLocal(
  command: string,
  args: readonly string[],
) {
  const spawner = yield* ChildProcessSpawner.ChildProcessSpawner;

  const handle = yield* spawner.spawn(
    ChildProcess.make(command, [...args], {
      stderr: "inherit",
      stdin: "inherit",
      stdout: "inherit",
    }),
  );

  const exitCode = yield* handle.exitCode;

  if (exitCode !== 0) {
    return yield* new GpuFailed({ message: `${command} exited with ${exitCode}` });
  }
}, Effect.scoped);

const rsyncExcludes = [".git", "node_modules", ".venv", "__pycache__", "dist", ".tanstack"].flatMap(
  (pattern) => ["--exclude", pattern],
);

const pushDir = Effect.fn("gpu.pushDir")(function* pushDir(ip: string, localDir: string) {
  const target = remoteDir(localDir);
  const options = yield* sshOptions();

  yield* runLocal("ssh", [...options, `root@${ip}`, `mkdir -p ${target}`]);
  yield* runLocal("rsync", [
    "-az",
    "--delete",
    ...rsyncExcludes,
    "-e",
    `ssh ${options.join(" ")}`,
    `${localDir.replace(/\/+$/u, "")}/`,
    `root@${ip}:${target}/`,
  ]);

  return target;
});

const nameArgument = Argument.String("name").pipe(
  Argument.withDescription("VM name or ID from `pnpm j gpu ls`"),
);

const ssh = Command.make(
  "ssh",
  {
    name: nameArgument,
    command: Argument.String("command").pipe(
      Argument.withDescription("Command to run on the VM. Leave it out for an interactive shell."),
      Argument.variadic(),
    ),
  },
  Effect.fn("gpu.ssh")(function* ssh({ command, name }) {
    const ip = yield* runningIp(name);
    const options = yield* sshOptions();

    yield* runLocal("ssh", [
      ...options,
      ...(command.length === 0 ? [] : ["-T"]),
      `root@${ip}`,
      ...command,
    ]);
  }),
).pipe(Command.withDescription("Open a shell on a VM, or run one command on it"));

const push = Command.make(
  "push",
  {
    name: nameArgument,
    dir: Argument.String("dir").pipe(Argument.withDescription("Local directory to copy")),
  },
  Effect.fn("gpu.push")(function* push({ dir, name }) {
    const ip = yield* runningIp(name);
    const target = yield* pushDir(ip, dir);

    yield* Console.log(`synced ${dir} to ${name}:${target}`);
  }),
).pipe(Command.withDescription("Copy a local directory to /root/work/<dir name> on a VM"));

const pull = Command.make(
  "pull",
  {
    name: nameArgument,
    remote: Argument.String("remote").pipe(
      Argument.withDescription("Path on the VM, such as /root/work/train/out"),
    ),
    local: Argument.String("local").pipe(Argument.withDescription("Local directory to copy into")),
  },
  Effect.fn("gpu.pull")(function* pull({ local, name, remote }) {
    const ip = yield* runningIp(name);
    const options = yield* sshOptions();

    yield* runLocal("rsync", [
      "-az",
      "-e",
      `ssh ${options.join(" ")}`,
      `root@${ip}:${remote}`,
      local,
    ]);
    yield* Console.log(`copied ${name}:${remote} to ${local}`);
  }),
).pipe(Command.withDescription("Copy results from a VM to this machine"));

const run = Command.make(
  "run",
  {
    name: nameArgument,
    dir: Argument.String("dir").pipe(
      Argument.withDescription("Local project directory to sync first"),
    ),
    command: Argument.String("command").pipe(
      Argument.withDescription(
        "Command to run inside the synced directory, such as `python train.py`",
      ),
      Argument.variadic(),
    ),
  },
  Effect.fn("gpu.run")(function* run({ command, dir, name }) {
    if (command.length === 0) {
      return yield* new GpuFailed({
        message: "Give a command after `--`, such as: -- python train.py --epochs 3",
      });
    }

    const ip = yield* runningIp(name);
    const target = yield* pushDir(ip, dir);
    const options = yield* sshOptions();
    const job = command.join(" ").replaceAll("'", `'\\''`);

    const setup = [
      "export PATH=$HOME/.local/bin:$PATH",
      "command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh",
      "[ -d .venv ] || uv venv -q --python 3.12",
      ". .venv/bin/activate",
      "if [ -f requirements.txt ]; then uv pip install -q -r requirements.txt; fi",
    ].join(" && ");

    yield* runLocal("ssh", [
      ...options,
      "-T",
      `root@${ip}`,
      `cd ${target} && nohup bash -lc '${setup} && ${job}; echo "exit $?" > run.exit' > run.log 2>&1 < /dev/null & echo started`,
    ]);

    yield* Console.log(`running in ${name}:${target}. It keeps running if you disconnect.`);
    yield* Console.log(`log:    pnpm j gpu ssh ${name} 'tail -n 50 ${target}/run.log'`);
    yield* Console.log(
      `done?:  pnpm j gpu ssh ${name} 'cat ${target}/run.exit'   (exists when the job ends)`,
    );
    yield* Console.log(`result: pnpm j gpu pull ${name} ${target}/out ./`);
  }),
).pipe(
  Command.withDescription(
    "Sync a directory to a VM and start a command there in the background, in a uv venv with requirements.txt",
  ),
);

export const gpu = Command.make("gpu").pipe(
  Command.withDescription("Team GPU VMs on Verda: types, up, ls, run, ssh, push, pull, down"),
  Command.withSubcommands([types, up, list, run, ssh, push, pull, down]),
);

export { GpuFailed };
