repertoire_chantier=$1
repertoire_BD_Uni=${2}
chemin_emprise=${3:-None}


repertoire_goutiere=${repertoire_chantier}/gouttieres

echo "Regroupement des géométries jointives dans la BD Uni"
python recalage/dissolve.py --input ${repertoire_BD_Uni} --output ${repertoire_goutiere}/BD_Uni_regroupee

python recalage/nettoyage.py --input ${repertoire_goutiere}/BD_Uni_regroupee --output ${repertoire_goutiere}/BD_Uni_nettoyee

echo "Ajustement des intersections sur les gouttières calculées"
python recalage/ajuster_intersection.py --input ${repertoire_goutiere}/intersections --emprise ${chemin_emprise} --output ${repertoire_goutiere}/intersections_ajustees


echo "Association des bâtiments gouttières / BD Uni"
python recalage/association_bati_BD_UNI.py --input_gouttieres ${repertoire_goutiere}/intersections_ajustees/intersections_ajustees.shp --input_BD_Uni ${repertoire_goutiere}/BD_Uni_nettoyee/BD_TOPO.gpkg --output ${repertoire_goutiere}/association_bati_BD_Uni

echo "Association des segments gouttières / BD Uni"
python recalage/association_segments_BD_UNI.py --input ${repertoire_goutiere}/association_bati_BD_Uni --output ${repertoire_goutiere}/association_segments_BD_Uni

echo "Calcul des paramètres pour recaler la BD Uni"
python recalage/recalage.py --input ${repertoire_goutiere}/association_segments_BD_Uni --output ${repertoire_goutiere}/recalage

echo "Application des paramètres sur la BD Uni"
python recalage/appliquer_recalage.py --input_gouttieres ${repertoire_goutiere}/recalage --input_BD_Uni ${repertoire_BD_Uni} --output ${repertoire_goutiere}/BD_Uni_recalee