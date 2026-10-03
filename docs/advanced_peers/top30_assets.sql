-- Bind p to joined Parquet and unknown to frozen baseline LEIs in top30_selection.json.
with cells as (
select lei,entityID,scope,bank_name,country,refPeriod,template_id,min(fact_value_eur) assets_eur,
count(distinct fact_value_raw) raw_values,count(distinct coalesce(open_axis_dims,'')) dimensions
from p join unknown using(lei)
where template_id in ('70.00','64.01.B') and cell_row='0010' and cell_col='0010'
and fact_value_eur>0 and not coalesce(unit_ambiguous,false)
group by 1,2,3,4,5,6,7
), preferred as (
select *,row_number() over(partition by lei order by refPeriod desc,case when scope='CON' then 0 else 1 end,case when template_id='70.00' then 0 else 1 end) n
from cells where raw_values=1 and dimensions=1
) select lei,entityID,scope,bank_name,country,refPeriod,template_id,assets_eur from preferred where n=1 order by assets_eur desc,lei;
