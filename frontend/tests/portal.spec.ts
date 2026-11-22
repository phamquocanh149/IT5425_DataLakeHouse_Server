import {test, expect, Page} from '@playwright/test';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';

async function login(page: Page, name = 'Minh Anh') {
  await page.goto('/portal/');
  await page.getByRole('link', {name: 'Đăng nhập bằng tài khoản tổ chức'}).click();
  await page.getByRole('link', {name: new RegExp(name)}).click();
  await expect(page.getByRole('heading', {name: 'Tổng quan workspace'})).toBeVisible();
}

async function detail(page: Page) {
  await page.getByRole('button', {name: 'Danh mục dữ liệu', exact: true}).click();
  await page.getByRole('button', {name: 'Xem dữ liệu', exact: true}).first().click();
  await expect(page.getByText('3.259', {exact: true})).toBeVisible();
}

test('USDM current, all layer downloads, maps and metadata', async ({page}) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await login(page);
  await expect(page.getByText('423.670', {exact: true})).toBeVisible();
  await page.screenshot({path: 'test-results/overview.png', fullPage: true});
  await detail(page);
  for (const layer of ['bronze', 'silver', 'gold']) {
    await page.locator('.layer-tabs button').filter({hasText: layer}).click();
    const downloadButton = page.getByRole('button', {name: /^Tải (ZIP|GeoParquet|CSV)$/});
    await expect(downloadButton).toBeEnabled();
    const responsePromise = page.waitForResponse(r => r.url().endsWith('/download'));
    const downloadPromise = page.waitForEvent('download');
    await downloadButton.click();
    const response = await responsePromise;
    const download = await downloadPromise;
    expect(response.status()).toBe(200);
    const bytes = await readFile((await download.path())!);
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(response.headers()['x-content-sha256']);
    for (const tab of ['Schema', 'Quality', 'Lineage']) {
      await page.getByRole('tab', {name: tab, exact: true}).click();
      await expect(page.getByRole('alert')).toHaveCount(0);
      await expect(page.locator('.detail-content .loading')).toHaveCount(0);
    }
    if (layer !== 'bronze') {
      const mapResponse = page.waitForResponse(r => r.url().includes('/map?'));
      await page.getByRole('tab', {name: 'Bản đồ', exact: true}).click();
      const result = await mapResponse;
      expect(result.status()).toBe(200);
      expect((await result.json()).features.length).toBeGreaterThan(0);
      await expect(page.locator('.maplibregl-canvas')).toBeVisible();
      await expect.poll(async () => Number(await page.locator('.map-container').getAttribute('data-rendered-features'))).toBeGreaterThan(0);
      await page.screenshot({path: `test-results/${layer}-map.png`, fullPage: true});
    }
  }
  expect(errors).toEqual([]);
  await page.getByRole('button', {name: 'Đăng xuất', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Chào mừng trở lại'})).toBeVisible();
  expect((await page.request.get('/api/portal/v1/overview')).status()).toBe(401);
});

test('restricted viewer and mobile layout', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await login(page, 'Khách');
  await detail(page);
  await expect(page.locator('.layer-tabs button')).toHaveCount(1);
  await expect(page.getByRole('button', {name: 'Tải CSV', exact: true})).toBeDisabled();
  expect((await page.request.get('/api/portal/v1/admin/users')).status()).toBe(403);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: 'test-results/mobile.png', fullPage: true});
});

test('operator saved attempts and admin grants drawer', async ({page}) => {
  await login(page, 'Hoàng Nam');
  await detail(page);
  await page.getByRole('tab', {name: 'Xử lý', exact: true}).click();
  await expect(page.getByText('Lịch sử tại snapshot; không phải trạng thái đang chạy.')).toBeVisible();
  await page.getByRole('button', {name: 'Đăng xuất', exact: true}).click();
  await login(page, 'Quản trị');
  await page.getByRole('button', {name: 'Quản lý quyền', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Quản lý quyền'})).toBeVisible();
  await page.screenshot({path: 'test-results/admin.png', fullPage: true});
});

test('loading, empty, recoverable error and expired session states', async ({page}) => {
  await login(page);
  await detail(page);
  await page.route('**/layers/gold/preview*', async route => {
    await new Promise(resolve => setTimeout(resolve, 700));
    await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({error: {code: 'STORAGE_UNAVAILABLE', message: 'Storage unavailable'}, request_id: 'ui-fault-test'})});
  });
  await page.getByRole('tab', {name: 'Schema', exact: true}).click();
  await page.getByRole('tab', {name: 'Dữ liệu', exact: true}).click();
  await expect(page.getByRole('status', {name: 'Đang tải dữ liệu'})).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('ui-fault-test');
  await page.unroute('**/layers/gold/preview*');
  await page.getByRole('button', {name: 'Thử lại', exact: true}).click();
  await expect(page.getByText('3.259', {exact: true})).toBeVisible();
  await page.getByLabel('Mã grid').fill('grid-that-does-not-exist');
  await page.getByRole('button', {name: 'Lọc', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Không có bản ghi phù hợp'})).toBeVisible();
  await page.context().clearCookies();
  await page.getByRole('tab', {name: 'Quality', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Chào mừng trở lại'})).toBeVisible();
});
