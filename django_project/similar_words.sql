select a.id, a.text, b.id, b.text
  from opp_word a
       inner join opp_word b
          on length(a.text) > 3
             and a.id != b.id
             and length(a.text) <= length(b.text)
             and length(b.text) <= length(a.text) + 4
             and b.text like substr(a.text, 1, length(a.text) - 1) || '%'
 where not exists (select null
                     from opp_synonym
                    where word_id = a.id and synonym_id = b.id)
 order by a.text;

