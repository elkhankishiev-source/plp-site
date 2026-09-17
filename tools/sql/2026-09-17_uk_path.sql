-- Путь «мой объект → договор с УК → аренда на сайте», 17.09.2026.
-- Эльнур: «в кабинете у владельца определённые объекты, он может выбрать любой и
-- поэтапно пройти путь к подписанию контракта с УК, выгрузить объект в блок аренды…
-- всё должно быть подвязано, функционировать, едино».
--
-- Лестница уже была — функция uk_ready. Не работало всё, что должно её кормить:
--   • uk_doc_file_add обращалась к uk_contracts.owner_client_id — такой колонки нет,
--     значит загрузка документа к объекту падала ВСЕГДА (в client_docs 21 строка и
--     все с пометкой «import» — через кабинет не загрузили ни одного файла);
--   • загруженный файл ложился в client_docs, а uk_ready читает uk_documents —
--     лестница не позеленела бы, даже если бы загрузка работала;
--   • договор управления нельзя было записать ниоткуда: ни одной функции записи
--     в uk_contracts во всей системе, только чтение из восьми мест;
--   • публикация на витрине шла мимо лестницы (Manor S14 висит в аренде с
--     blocker = no_contract).

-- 1. Владелец у договора. Колонку ждал код, её не было.
alter table public.uk_contracts add column if not exists owner_client_id uuid;

update public.uk_contracts c
   set owner_client_id = a.client_id
  from public.owner_properties p
  join public.owner_accounts a on a.id = p.owner_id
 where p.plp_property_id = c.property_id
   and c.owner_client_id is null
   and a.client_id is not null;

-- 2. Кто имеет право трогать объект: сотрудник или владелец этого объекта.
create or replace function public.uk_may_touch(p_token text, p_property text)
returns jsonb language plpgsql security definer set search_path to 'public' as $$
declare v_owner uuid; v_cid uuid; v_staff boolean; v_who text; v_own boolean;
begin
  select s.owner_id, a.client_id, coalesce(a.is_staff,false), a.name
    into v_owner, v_cid, v_staff, v_who
    from owner_sessions s join owner_accounts a on a.id = s.owner_id
   where s.token = p_token and s.expires_at > now();
  if v_who is null then return jsonb_build_object('ok',false,'error','no_session'); end if;
  select exists(select 1 from owner_properties
                 where owner_id = v_owner and plp_property_id = p_property) into v_own;
  return jsonb_build_object('ok', (v_staff or v_own), 'staff', v_staff, 'owner_id', v_owner,
                            'client_id', v_cid, 'who', v_who, 'mine', v_own,
                            'error', case when (v_staff or v_own) then null else 'not_yours' end);
end $$;

-- 3. Документ к объекту: живой путь и запись СРАЗУ в оба места.
--    client_docs — файл человека, uk_documents — то, что читает лестница.
create or replace function public.uk_doc_file_add(
  p_token text, p_property text, p_name text, p_key text, p_mime text,
  p_size bigint, p_kind text default 'contract')
returns jsonb language plpgsql security definer set search_path to 'public' as $$
declare v_may jsonb; v_cid uuid; v_id bigint; v_title text;
begin
  if coalesce(p_property,'') = '' then
    return jsonb_build_object('ok', false, 'error', 'не выбран объект');
  end if;
  v_may := uk_may_touch(p_token, p_property);
  if not (v_may->>'ok')::boolean then return v_may; end if;

  select owner_client_id into v_cid from uk_contracts
   where property_id = p_property and coalesce(status,'active') <> 'cancelled'
   order by created_at desc limit 1;
  v_cid := coalesce(v_cid, (v_may->>'client_id')::uuid);

  insert into client_docs (client_id, kind, file_name, storage_key, mime, size_bytes,
                           object_id, uploaded_by)
  values (v_cid, coalesce(nullif(p_kind,''),'contract'), left(p_name,200), p_key,
          p_mime, p_size, p_property, left(coalesce(v_may->>'who','кабинет'),60))
  returning id into v_id;

  -- название с видом документа: лестница узнаёт бумагу по словам, а не по расширению
  v_title := case coalesce(nullif(p_kind,''),'contract')
    when 'accept'    then 'Акт приёмки — ' when 'inventory' then 'Опись имущества — '
    when 'rules'     then 'Правила проживания — ' when 'management' then 'Договор управления — '
    else '' end || left(coalesce(p_name,'файл'),160);
  insert into uk_documents (property_id, title, kind, url, note, added_by, visible_to_owner)
  values (p_property, v_title, coalesce(nullif(p_kind,''),'contract'), p_key,
          'загружено в кабинете', left(coalesce(v_may->>'who','кабинет'),60), true);

  return jsonb_build_object('ok', true, 'doc_id', v_id);
end $$;

-- 4. Тот же файл, но когда объект не выбран (личная папка) — с необязательной привязкой.
create or replace function public.client_doc_add(
  p_token text, p_name text, p_key text, p_mime text, p_size bigint,
  p_kind text default 'contract', p_property text default null)
returns jsonb language plpgsql security definer set search_path to 'public' as $$
declare v_cid uuid; v_id bigint; v_code text;
begin
  if coalesce(p_property,'') <> '' then
    return uk_doc_file_add(p_token, p_property, p_name, p_key, p_mime, p_size, p_kind);
  end if;
  select a.client_id into v_cid
    from owner_sessions s join owner_accounts a on a.id = s.owner_id
   where s.token = p_token and s.expires_at > now();
  if v_cid is null then return jsonb_build_object('ok', false, 'error', 'no_session'); end if;

  insert into client_docs (client_id, kind, file_name, storage_key, mime, size_bytes)
  values (v_cid, coalesce(nullif(p_kind,''),'contract'), left(p_name,200), p_key, p_mime, p_size)
  returning id into v_id;
  select code into v_code from clients where client_id = v_cid;
  insert into client_timeline (client_id, kind, title, body, actor)
  values (v_cid, 'doc', 'Прислал документ: ' || coalesce(p_name,'файл'),
          'Разбираем и заполняем карточку', 'client');
  return jsonb_build_object('ok', true, 'doc_id', v_id, 'code', v_code, 'client_id', v_cid);
end $$;

-- 5. Запись договора управления. Раньше строку в uk_contracts можно было завести
--    только руками в базе — поэтому шаг 1 лестницы не зеленел ни у кого.
create or replace function public.uk_contract_set(
  p_token text, p_property text, p_owner_name text default null,
  p_owner_phone text default null, p_owner_email text default null,
  p_rental_type text default 'mixed', p_short numeric default null,
  p_long numeric default null, p_start date default null, p_end date default null,
  p_status text default 'active', p_payout text default null)
returns jsonb language plpgsql security definer set search_path to 'public' as $$
declare v_may jsonb; v_id bigint; v_own uuid;
begin
  v_may := uk_may_touch(p_token, p_property);
  if not (v_may->>'ok')::boolean then return v_may; end if;
  if not (v_may->>'staff')::boolean then
    return jsonb_build_object('ok', false, 'error', 'only_staff',
      'msg', 'Договор в систему заводит менеджер — пришлите подписанный файл, мы его проведём.');
  end if;
  if not exists (select 1 from objects where plp_property_id = p_property) then
    return jsonb_build_object('ok', false, 'error', 'no_object');
  end if;

  select a.client_id into v_own from owner_properties p
    join owner_accounts a on a.id = p.owner_id
   where p.plp_property_id = p_property limit 1;

  select id into v_id from uk_contracts where property_id = p_property
   order by created_at desc limit 1;
  if v_id is null then
    insert into uk_contracts (property_id, owner_name, owner_phone, owner_email,
      rental_type, commission_short_pct, commission_long_pct, start_date, end_date,
      status, payout_details, owner_client_id, currency)
    values (p_property, p_owner_name, p_owner_phone, p_owner_email,
      coalesce(p_rental_type,'mixed'), p_short, p_long, p_start, p_end,
      coalesce(p_status,'active'), p_payout, v_own, 'THB')
    returning id into v_id;
  else
    update uk_contracts set
      owner_name = coalesce(p_owner_name, owner_name),
      owner_phone = coalesce(p_owner_phone, owner_phone),
      owner_email = coalesce(p_owner_email, owner_email),
      rental_type = coalesce(p_rental_type, rental_type),
      commission_short_pct = coalesce(p_short, commission_short_pct),
      commission_long_pct = coalesce(p_long, commission_long_pct),
      start_date = coalesce(p_start, start_date),
      end_date = coalesce(p_end, end_date),
      status = coalesce(p_status, status),
      payout_details = coalesce(p_payout, payout_details),
      owner_client_id = coalesce(owner_client_id, v_own)
    where id = v_id;
  end if;
  return jsonb_build_object('ok', true, 'contract_id', v_id, 'ready', uk_ready(p_property));
end $$;

-- 6. Публикация спрашивает лестницу. Без этого «выгрузить в аренду» = правка базы руками.
create or replace function public.uk_publish(
  p_token text, p_property text, p_on boolean default true)
returns jsonb language plpgsql security definer set search_path to 'public' as $$
declare v_may jsonb; v_r jsonb;
begin
  v_may := uk_may_touch(p_token, p_property);
  if not (v_may->>'ok')::boolean then return v_may; end if;
  if not (v_may->>'staff')::boolean then
    return jsonb_build_object('ok', false, 'error', 'only_staff',
      'msg', 'Публикацию подтверждает менеджер: он сверяет документы и ставки.');
  end if;
  if not p_on then
    update objects set on_site = false where plp_property_id = p_property;
    return jsonb_build_object('ok', true, 'on_site', false);
  end if;
  v_r := uk_ready(p_property);
  if not coalesce((v_r->>'can_publish')::boolean, false) then
    return jsonb_build_object('ok', false, 'error', 'not_ready',
      'msg', coalesce(nullif(v_r->>'msg',''),
             'Не хватает бумаг: до витрины нужны акт приёмки и опись загруженными файлами.'),
      'ready', v_r);
  end if;
  update objects set on_site = true, purpose = coalesce(nullif(purpose,''),'аренда')
   where plp_property_id = p_property;
  return jsonb_build_object('ok', true, 'on_site', true, 'ready', v_r,
    'msg', 'Объект выйдет на витрину после ближайшей пересборки каталога.');
end $$;

-- 7. Старая шестиаргументная версия остаётся рядом с новой и делает выбор функции
--    неоднозначным. Закон одного экземпляра: лишнюю убираем.
drop function if exists public.client_doc_add(text,text,text,text,bigint,text);
