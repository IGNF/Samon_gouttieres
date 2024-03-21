repertoire_chantier=$1
repertoire_BD_Uni=${2}
chemin_emprise=${3:-None}


repertoire_goutiere=${repertoire_chantier}/goutieres

sh run.sh ${repertoire_chantier} ${chemin_emprise}

echo "Regroupement des géométries jointives dans la BD Uni"
python dissolve.py --input ${repertoire_BD_Uni} --output ${repertoire_goutiere}/BD_Uni_regroupee

echo "Ajustement des intersections sur les gouttières calculées"
python ajuster_intersection.py --input ${repertoire_goutiere}/intersection_plan --emprise ${chemin_emprise} --output ${repertoire_goutiere}/intersections_ajustees


echo "Association des bâtiments gouttières / BD Uni"
python association_bati_BD_UNI.py --input_gouttieres ${repertoire_goutiere}/intersections_ajustees --input_BD_Uni ${repertoire_goutiere}/BD_Uni_regroupee --output ${repertoire_goutiere}/association_bati_BD_Uni

echo "Association des segments gouttières / BD Uni"
python association_segments_BD_UNI.py --input ${repertoire_goutiere}/association_bati_BD_Uni --output ${repertoire_goutiere}/association_segments_BD_Uni

echo "Calcul des paramètres pour recaler la BD Uni"
python recalage.py --input ${repertoire_goutiere}/association_segments_BD_Uni --output ${repertoire_goutiere}/recalage

echo "Application des paramètres sur la BD Uni"
python appliquer_recalage.py --input_gouttieres ${repertoire_goutiere}/recalage --input_BD_Uni ${repertoire_BD_Uni} --output ${repertoire_goutiere}/BD_Uni_recalee