const assert = require('node:assert/strict');
const { resolve } = require('node:path');
const { test } = require('node:test');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

test('初次打开显示三条待办和总进度', async () => {
  const browser = await chromium.launch({ args: ['--single-process', '--no-zygote'] });
  try {
    const page = await browser.newPage();
    await page.goto(pathToFileURL(resolve(__dirname, '../index.html')).href);
    assert.equal(await page.getByRole('listitem').count(), 3);
    assert.equal(await page.locator('#summary').textContent(), '共 3 项，已完成 2 项');
  } finally {
    await browser.close();
  }
});
