const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

async function grade(runDir) {
  const project = path.join(runDir, 'workspace', 'task');
  const receipt = fs.readFileSync(path.join(runDir, 'receipt.md'), 'utf8');
  const links = [...receipt.matchAll(/\[[^\]\n]+\]\(<?([^)>\n]+)>?\)/g)].map((match) =>
    path.resolve(project, decodeURIComponent(match[1]).replace(/(?::\d+(?::\d+)?|#L\d+)$/, '')),
  );
  const checks = [];

  async function check(name, evaluate) {
    try {
      await evaluate();
      checks.push({ name, passed: true });
    } catch (error) {
      checks.push({ name, passed: false, detail: error.message });
    }
  }

  const browser = await chromium.launch({ args: ['--single-process', '--no-zygote'] });
  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(3000);
    await page.route(/^https?:/, (route) => route.abort());
    await page.goto(pathToFileURL(path.join(project, 'index.html')).href);
    const items = page.getByRole('listitem');
    const original = await items.allTextContents();
    await check('点击后只显示两条已完成事项，保留总进度', async () => {
      assert.equal(original.length, 3);
      await page.getByRole('button', { name: '只看已完成', exact: true }).click();
      assert.deepEqual(await items.allTextContents(), [original[0], original[2]]);
      assert.equal(await page.getByRole('button', { name: '显示全部', exact: true }).count(), 1);
      assert.equal(await page.locator('#summary').textContent(), '共 3 项，已完成 2 项');
    });
    await check('点击显示全部恢复原顺序', async () => {
      await page.getByRole('button', { name: '显示全部', exact: true }).click();
      assert.deepEqual(await items.allTextContents(), original);
      assert.equal(await page.getByRole('button', { name: '只看已完成', exact: true }).count(), 1);
    });
  } finally {
    await browser.close();
  }

  await check('回执链接到实际改动的界面文件和脚本', () => {
    for (const name of ['index.html', 'app.js']) {
      const file = path.join(project, name);
      assert.ok(fs.existsSync(file) && links.includes(file), `缺少 ${name} 链接`);
    }
  });
  await check('回执引用了筛选脚本中实际新增的函数名', () => {
    const source = fs.readFileSync(path.join(project, 'app.js'), 'utf8');
    const names = [...source.matchAll(/\bfunction\s+(\w+)\s*\(|\b(?:const|let)\s+(\w+)\s*=\s*(?:\([^)]*\)|\w+)\s*=>/g)]
      .map((match) => match[1] ?? match[2]).filter((name) => name !== 'updateSummary');
    assert.ok(names.some((name) => new RegExp(`\\b${name}\\b`).test(receipt)), '回执未引用新增的筛选函数');
  });
  await check('回执提供 task 证据目录里的真实 PNG', () => {
    const pngSignature = '89504e470d0a1a0a';
    const taskDir = path.join(project, 'docs', 'spec', 'checklist', 'tasks', 'filter-completed', 'evidence') + path.sep;
    const screenshots = links.filter((file) =>
      file.startsWith(taskDir) && file.endsWith('.png') && fs.existsSync(file),
    );
    assert.ok(screenshots.some((file) => fs.readFileSync(file).subarray(0, 8).toString('hex') === pngSignature), '缺少可打开的 PNG 附件');
  });

  await check('xdev check 通过（覆盖率 100%、用例对应到真实测试）', () => {
    const { execFileSync } = require('node:child_process');
    const tool = path.join(runDir, 'workspace', 'skills', 'x-dev', 'scripts', 'xdev.py');
    execFileSync('python3', [tool, 'check', path.join(project, 'docs/spec/checklist/tasks/filter-completed')], { cwd: project, stdio: 'pipe' });
  });

  const passed = checks.filter((check) => check.passed).length;
  const result = { scope: 'x_dev_receipt', passed, total: checks.length, checks };
  fs.writeFileSync(path.join(runDir, 'grading.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(`${passed}/${checks.length} 通过`);
  for (const check of checks) {
    console.log(`${check.passed ? '通过' : '失败'} ${check.name}${check.detail ? ` (${check.detail})` : ''}`);
  }
  process.exitCode = passed === checks.length ? 0 : 1;
}

grade(path.resolve(process.argv[2])).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
