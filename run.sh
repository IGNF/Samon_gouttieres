repertoire_chantier=$1
chemin_emprise=${2:-None}

repertoire_goutiere=${repertoire_chantier}/gouttieres

echo ""
echo "Regroupement des géométries jointives"
python dissolve.py --input ${repertoire_goutiere}/predictions_FFL --output ${repertoire_goutiere}/regroupe

echo ""
echo "Nettoyage des géométries"
python nettoyage.py --input ${repertoire_goutiere}/regroupe --output ${repertoire_goutiere}/nettoye

echo ""
echo "Association d'un même identifiant aux bâtiments"
python association_bati.py --input ${repertoire_goutiere}/nettoye --mnt ${repertoire_chantier}/mnt --ta_xml ${repertoire_chantier}/orientation --raf ${repertoire_chantier}/raf --emprise ${chemin_emprise}  --output ${repertoire_goutiere}/association_bati

echo ""
echo "Association d'un même identifiant aux murs"
python association_segments.py --input ${repertoire_goutiere}/association_bati --mnt ${repertoire_chantier}/mnt --ta_xml ${repertoire_chantier}/orientation --raf ${repertoire_chantier}/raf  --output ${repertoire_goutiere}/association_segments

echo ""
echo "Calcul des gouttières"
python intersection_plan.py --input ${repertoire_goutiere}/association_segments --mnt ${repertoire_chantier}/mnt --ta_xml ${repertoire_chantier}/orientation --raf ${repertoire_chantier}/raf --pvas ${repertoire_chantier}/pvas --output ${repertoire_goutiere}/intersection_plan

echo "Fermeture des bâtiments"
python fermer_batiment.py --input ${repertoire_goutiere}/intersection_plan --output ${repertoire_goutiere}/batiments_fermes