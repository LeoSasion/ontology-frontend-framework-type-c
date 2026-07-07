import { spawnSync } from "node:child_process";

const projects = [
  "C:\\Users\\Administrator\\Documents\\AIBI",
  "C:\\Users\\Administrator\\Documents\\财务报表",
];

const results = projects.map((cwd) => {
  const result = spawnSync("git", ["-C", cwd, "status", "--short", "--branch"], {
    encoding: "utf8",
    windowsHide: true,
  });
  return {
    cwd,
    gitStatusAvailable: result.status === 0,
    stdout: result.stdout.trim(),
    stderr: result.stderr.trim(),
  };
});

console.log(JSON.stringify({ ok: true, results }, null, 2));
