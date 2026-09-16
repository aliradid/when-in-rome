// when-in-rome — OpenCode plugin.
//
// `skills/when-in-rome/SKILL.md` is the single source of truth.
//   • Registers the skills directory and a `/when-in-rome` command.
//   • Injects the repo's commit house style into the system prompt each turn
//     (the OpenCode equivalent of the Claude Code SessionStart hook).
//   • Before every bash tool call, runs the same checker the Claude Code
//     PreToolUse hook uses and refuses git commit / gh pr create commands whose
//     message would not pass as native to the repo.
//
// Install — add to opencode.json:
//   { "plugin": ["./.opencode/plugins/when-in-rome.mjs"] }
// Turn off:  WHEN_IN_ROME_OFF=1

import fs from 'fs';
import path from 'path';
import { spawnSync } from 'child_process';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '../..');
const skillsDir = path.join(root, 'skills');
const commandPath = path.join(__dirname, '..', 'command', 'when-in-rome.md');

async function commandDefinition() {
  const raw = await fs.promises.readFile(commandPath, 'utf8');
  const match = raw.match(/^---[^\S\r\n]*\r?\n([\s\S]*?)\r?\n---[^\S\r\n]*(?:\r?\n|$)([\s\S]*)$/);
  if (!match) throw new Error('Missing command frontmatter');
  return { ...JSON.parse(match[1]), template: match[2].trim() };
}

function runHook(script, payload) {
  const r = spawnSync('python3', [path.join(root, 'hooks', script)], {
    input: JSON.stringify(payload), encoding: 'utf8', timeout: 20000,
  });
  if (r.status !== 0 || !r.stdout) return null;
  try { return JSON.parse(r.stdout); } catch { return null; }
}

export default async ({ directory }) => {
  const cwd = directory || process.cwd();
  return {
    config: async (config) => {
      config.skills = config.skills || {};
      config.skills.paths = config.skills.paths || [];
      if (!config.skills.paths.includes(skillsDir)) config.skills.paths.push(skillsDir);
      try {
        config.command = config.command || {};
        if (!config.command['when-in-rome']) config.command['when-in-rome'] = await commandDefinition();
      } catch (e) { /* skill discovery must not break */ }
    },

    'experimental.chat.system.transform': async (_input, output) => {
      if (process.env.WHEN_IN_ROME_OFF) return;
      const out = runHook('sessionstart.py', { cwd });
      const ctx = out && out.hookSpecificOutput && out.hookSpecificOutput.additionalContext;
      if (!ctx) return;
      if (output.system.length > 0) output.system[output.system.length - 1] += '\n\n' + ctx;
      else output.system.push(ctx);
    },

    'tool.execute.before': async (input, output) => {
      if (process.env.WHEN_IN_ROME_OFF) return;
      if (!input || input.tool !== 'bash') return;
      const command = output && output.args && output.args.command;
      if (!command || !(command.includes('commit') || command.includes('pr'))) return;
      const out = runHook('pretooluse.py', { tool_name: 'Bash', cwd, tool_input: { command } });
      const h = out && out.hookSpecificOutput;
      if (h && h.permissionDecision === 'deny') throw new Error(h.permissionDecisionReason);
    },
  };
};
