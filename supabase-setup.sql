-- 爸~媽!!假日要去哪裡玩：留言、讚／倒讚、回報 的資料表
-- 用法：Supabase 專案 → SQL Editor → New query → 整段貼上 → Run

create table if not exists votes (
  item_key   text not null check (length(item_key) <= 200),
  device_id  text not null check (length(device_id) <= 64),
  val        smallint not null check (val in (-1, 0, 1)),
  updated_at timestamptz not null default now(),
  primary key (item_key, device_id)
);

create table if not exists comments (
  id         bigint generated always as identity primary key,
  item_key   text not null check (length(item_key) <= 200),
  item_name  text check (length(item_name) <= 200),
  nickname   text not null check (length(nickname) between 1 and 20),
  body       text not null check (length(body) between 1 and 300),
  device_id  text check (length(device_id) <= 64),
  hidden     boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists comments_item_idx on comments (item_key, created_at desc);

create table if not exists reports (
  id         bigint generated always as identity primary key,
  item_name  text check (length(item_name) <= 200),
  kind       text check (length(kind) <= 50),
  body       text not null check (length(body) between 1 and 1000),
  contact    text check (length(contact) <= 100),
  page       text check (length(page) <= 200),
  done       boolean not null default false,
  created_at timestamptz not null default now()
);

alter table votes    enable row level security;
alter table comments enable row level security;
alter table reports  enable row level security;

-- 讚：大家都能看、能新增、能改自己的（以裝置區分）
create policy votes_read   on votes for select to anon using (true);
create policy votes_insert on votes for insert to anon with check (true);
create policy votes_update on votes for update to anon using (true) with check (true);

-- 留言：大家看得到沒被隱藏的；只能新增，不能改別人的
create policy comments_read   on comments for select to anon using (not hidden);
create policy comments_insert on comments for insert to anon with check (hidden = false);

-- 回報：只能送出，外人讀不到（只有你在 Supabase 後台看得到）
create policy reports_insert on reports for insert to anon with check (true);

-- 每張卡片的讚數、倒讚數、留言數
create or replace view item_stats with (security_invoker = on) as
select coalesce(v.item_key, c.item_key) as item_key,
       coalesce(v.up, 0)   as up,
       coalesce(v.down, 0) as down,
       coalesce(c.n, 0)    as comments
from (select item_key,
             count(*) filter (where val = 1)  as up,
             count(*) filter (where val = -1) as down
      from votes group by item_key) v
full join (select item_key, count(*) as n
           from comments where not hidden group by item_key) c
  on v.item_key = c.item_key;

grant select on item_stats to anon;
grant select, insert, update on votes to anon;
grant select, insert on comments to anon;
grant insert on reports to anon;

-- ===== 推薦 + 管理後台（第二段，第一段跑過之後再跑這段也可以）=====
-- ⚠️ 下面這行改成「你自己的」Email，只有這個 Email 能在 admin.html 審核
create or replace function is_owner() returns boolean language sql stable as $$
  select coalesce(auth.jwt() ->> 'email', '') = 'willkao520@gmail.com'
$$;

create table if not exists suggestions (
  id          bigint generated always as identity primary key,
  kind        text not null check (kind in ('活動','公辦親子活動','共融公園','景點')),
  name        text not null check (length(name) between 1 and 100),
  county      text not null check (length(county) <= 10),
  district    text check (length(district) <= 20),
  dates       text check (length(dates) <= 60),
  link        text check (length(link) <= 300),
  note        text check (length(note) <= 500),
  contact     text check (length(contact) <= 100),
  status      text not null default 'pending' check (status in ('pending','approved','rejected')),
  reviewed_at timestamptz,
  created_at  timestamptz not null default now()
);
alter table suggestions enable row level security;

-- 任何人都能送推薦（只能是待審）
create policy sg_insert on suggestions for insert to anon, authenticated with check (status = 'pending');
-- 通過的推薦公開可讀（每天的自動更新靠這個讀取）
create policy sg_read_approved on suggestions for select to anon using (status = 'approved');
-- 你（管理者）可以看全部、改狀態
create policy sg_owner_read   on suggestions for select to authenticated using (is_owner());
create policy sg_owner_update on suggestions for update to authenticated using (is_owner()) with check (is_owner());

-- 管理者可以看回報、標記已處理
create policy reports_owner_read   on reports for select to authenticated using (is_owner());
create policy reports_owner_update on reports for update to authenticated using (is_owner()) with check (is_owner());

grant insert on suggestions to anon, authenticated;
grant select on suggestions to anon, authenticated;
grant update on suggestions to authenticated;
grant select, update on reports to authenticated;
grant insert on reports to authenticated;
grant select, insert, update on votes to authenticated;
grant select, insert on comments to authenticated;
grant select on item_stats to authenticated;

-- ===== 使用分析（第三段）=====
create table if not exists analytics (
  id     bigint generated always as identity primary key,
  ts     timestamptz not null default now(),
  type   text not null check (length(type) <= 20),
  label  text check (length(label) <= 200),
  item   text check (length(item) <= 200),
  extra  jsonb,
  sid    text check (length(sid) <= 40),
  dev    text check (length(dev) <= 64)
);
create index if not exists analytics_ts_idx on analytics (ts desc);
alter table analytics enable row level security;
create policy an_insert on analytics for insert to anon, authenticated with check (true);
create policy an_owner_read on analytics for select to authenticated using (is_owner());
grant insert on analytics to anon, authenticated;
grant select on analytics to authenticated;

-- ===== 留言管理權限（第三段：讓管理者在後台隱藏／刪除留言）=====
grant select, update, delete on comments to authenticated;
drop policy if exists comments_owner_read   on comments;
drop policy if exists comments_owner_update on comments;
drop policy if exists comments_owner_delete on comments;
create policy comments_owner_read   on comments for select to authenticated using (is_owner());
create policy comments_owner_update on comments for update to authenticated using (is_owner()) with check (is_owner());
create policy comments_owner_delete on comments for delete to authenticated using (is_owner());
