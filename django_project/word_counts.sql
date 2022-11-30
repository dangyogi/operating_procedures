select text, count(*) from opp_wordref r inner join opp_word w on r.word_id = w.id
 group by text having count(*) > 2
 order by 2;
