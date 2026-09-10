/* 🔴 10.09 Эльнур: «открыть удалить есть, редактировать нет». Черновик можно
   было только выбросить и собрать заново. Меняем название, текст и темп;
   получателей не трогаем — для них текст пересобирается заново. */
create or replace function public.campaign_edit(
  p_id bigint, p_name text default null, p_template text default null,
  p_per_day int default null, p_actor text default 'manager')
returns jsonb language plpgsql security definer set search_path = public as $fn$
declare c record; v_n int := 0;
begin
  select * into c from campaigns where id = p_id;
  if not found then return jsonb_build_object('ok', false, 'error', 'нет такой рассылки'); end if;
  if c.status not in ('draft','paused') then
    return jsonb_build_object('ok', false, 'error',
      'менять можно только черновик или остановленную. Эта — ' || c.status);
  end if;

  if p_template is not null and (p_template ~ '\{\{'
     or (select count(*) from regexp_matches(p_template, '\{([^}]*)\}', 'g') m
          where m[1] not in ('имя','код','объект')) > 0) then
    return jsonb_build_object('ok', false, 'error',
      'в тексте есть подстановка, которой мы не знаем. Разрешены только {имя}, {код} и {объект}');
  end if;

  update campaigns set
    name = coalesce(nullif(trim(p_name),''), name),
    template = coalesce(nullif(trim(p_template),''), template),
    per_day = coalesce(greatest(1, least(p_per_day, 50)), per_day)
   where id = p_id;

  /* текст поменялся — пересобираем его тем, кому ещё не ушло */
  if p_template is not null and nullif(trim(p_template),'') is not null then
    with upd as (
      update campaign_targets t set text_final =
        replace(replace(replace(p_template,
          '{имя}', coalesce(nullif(cl.name,''), 'Здравствуйте')),
          '{код}', cl.code),
          '{объект}', coalesce((select coalesce(o.project_name, o.object_id) from client_objects o
                                 where o.client_id = cl.client_id and o.rel = 'owns' limit 1),
                               'вашему объекту'))
      from clients cl
      where t.campaign_id = p_id and t.status = 'pending' and cl.client_id = t.client_id
      returning 1)
    select count(*) into v_n from upd;
  end if;

  return jsonb_build_object('ok', true, 'обновлено_текстов', v_n);
end $fn$;
revoke execute on function public.campaign_edit(bigint,text,text,int,text) from public, anon, authenticated;
notify pgrst, 'reload schema';
