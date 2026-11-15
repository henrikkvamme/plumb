const major = Number(process.versions.node.split(".")[0]);

if (major < 24) {
  process.stderr.write(
    `pnpm j needs Node 24 or newer, and this shell runs Node ${process.versions.node}. Fix: run \`nix shell nixpkgs#nodejs_24\`, or put Node 24 first on PATH, then run the command again.\n`,
  );
  process.exitCode = 1;
}
