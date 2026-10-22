## Mise en situation D'intégration continu \- data

L’objet de cette mise en situation est d’utiliser les outils d’intégration continue afin de s’assurer de la qualité d’une pipeline data. 

Pour cela vous aurez à déployer l’ensemble des outils nécessaire à une pipeline data qui part de données csv jusqu’à insertion dans une base de donnée relationnelle et connexion à un dashboard. 

Le sujet est découpé en niveau. 

**Niveau 1**   
1\. Faire un script qui génère plusieurs  csv avec 5 à 10 des transactions financières  au format suivant : 

- datetime transaction  
- iban origine  
- pays source  
- banque source  
- iban destinataire  
- pays destinataire

il faudra mettre des données non aléatoire pour rendre testable la pipeline

2\. Faire un script / lib python qui charge les données et fait le traitement des données suivantes : 

- fais la somme des montants envoyé par iban origine  
- fais la somme des montants envoyés par banque source  
- fais la somme des montants reçus par iban   
- flag la transaction si le montant est au dessus de 5000 

Vous séparerez les fonctions de chargement de données des fonctions de traitemnet qui doivent être pure

3\. Concevoir une base de données relationnelle pour accueillir les résultats des traitement. Mettre à jour le script pour avoir une fonction d’insertion des données. \*

4\. Faire une pipeline qui génère le fichier csv, lance le script de traitement, setup une base de données relationnelle et fais l’insertion des données. 

5\. Faites un test d’intégration automatique pour que les données insérées dans la base ont les bonnes valeurs / état

6\. En faisant des captures d’écran faites un scenario ou la pipeline échoue que ça soit via un bug dans la génération des données ou le traitement. 

7\. Simuler un bug d’insertion des données dans la base et proposer un mécanisme de retry pour réinsérer en cas de problème. 

Remarques : 

- Vous devrez éviter à tout pris de traiter deux fois le même fichier csv même en cas de retry. Penser à un mécanisme qui permet d’éviter de retraiter un fichier déjà traité. 


  
**Niveau 2**

1\. Désormais les fichiers csv doivent être stockés non plus dans le même dossier que le script de projet mais dans un service S3 (simple storage service).   
Afin de ne pas utiliser un service S3 d’un cloud provider dans la pipeline, vous décidez d’utiliser un service S3 local comme Garage, SeaweedFS, RustFs ou toute autre alternative. 

2\. Faire en sorte désormais que les fichiers csv soient mis dans le S3 qui sera lancé en début de pipeline. 

3\. Faire en sorte que le système de traitement des données récupère les données depuis le S3 local et non plus du file système local. 

4\. Faire en sorte d’implémenter un système de retry au cas où le fichier en cours de récupération ne se récupère pas.

   
**Niveau 3** Implémenter 1 ou plusieurs améliorations 

- faire en sorte d’avoir une pipeline CD qui déploie via docker le setup de production sur une machine virtuel ou sur un kubernetes:   
  - le S3  
  - la base de données  
  - le script de traitement des données avec un mécanisme pour lancer régulièrement le script au cas où de données données soient à traiter

- Faire en sorte que votre pipeline utilise un OCR pour extraire également des données de transaction contenus dans des images   
- Utiliser un SLS (small language model) pour que votre pipeline extrait des données de transactions contenues dans des texts bruts  
- Utiliser terraform / open tofu pour deployer les ressources productions dans le cloud (S3, kubernetes managé, db et / ou vm)