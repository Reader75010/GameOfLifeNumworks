"""
Amélioration du jeu de la vie pour NumWorks :

Cette version du script ajoute la répétition automatique des actions
associées aux touches lorsque celles‑ci sont maintenues enfoncées. Dans
la version originale, chaque appui de touche déclenchait une action
unique et le programme attendait que la touche soit relâchée avant
d’accepter un nouvel événement. Le nouveau comportement permet de
déplacer le curseur en continu en maintenant les flèches, de lancer
l’évolution du plateau, de vider ou de remplir la grille plusieurs
fois sans avoir à relâcher la touche entre chaque action.

Principales modifications :
  * Introduction du module ``time`` de MicroPython pour réaliser de
    petites pauses entre deux actions consécutives (``sleep_ms``).
  * Réécriture de ``main_loop`` pour ne plus attendre le relâchement
    des touches. La boucle principale teste en permanence l’état des
    touches et exécute l’action correspondante. Après chaque action,
    une courte pause est effectuée afin d’éviter une répétition trop
    rapide.

Les autres fonctions et la structure générale (``Game``, ``Cursor``)
restent inchangées et conservent leurs rôles d’origine.
"""

from ion import *
from math import ceil
from kandinsky import *
from random import getrandbits
import time

# Tentative d'importation du module gc pour gérer la mémoire. Le module
# ``gc`` n'est pas disponible sur toutes les versions de l'OS NumWorks,
# c'est pourquoi on capture ImportError. Si l'import échoue, la variable
# ``gc`` vaudra ``None`` et les appels à ``gc.collect()`` seront
# conditionnés.
try:
    import gc  # type: ignore
except ImportError:
    gc = None


class Game:
    def __init__(self, case_size):
        # Taille de l'écran en pixels (NumWorks)
        self.screen_size = (320, 222)
        # Taille d'une case de la grille en pixels
        self.size_of_case = case_size
        # Nombre de cases selon les dimensions choisies
        self.num_of_cases_in_x = ceil(self.screen_size[0] / self.size_of_case)
        self.num_of_cases_in_y = ceil(self.screen_size[1] / self.size_of_case)
        # Dictionnaire de couleurs utilisées
        self.colors = {
            "gridColor": color(128, 128, 128),
            "cursorWhiteColor": color(200, 200, 200),
            "cursorBlackColor": color(50, 50, 50),
            "whiteColor": color(255, 255, 255),
            "blackColor": color(0, 0, 0),
        }
        # Grille logique de l'état des cellules (vivantes ou mortes)
        self.map = [[False] * self.num_of_cases_in_y for _ in range(self.num_of_cases_in_x)]
        # Instanciation du curseur de sélection
        self.cursor = Cursor(self)
        # Dernier état connu de la touche OK pour détecter les transitions
        self._ok_last_state = False
        # Historique des générations : à chaque appel de ``update_map``, on
        # enregistre une copie de la grille actuelle pour pouvoir revenir en
        # arrière avec la touche d'undo. La liste fonctionne comme une
        # pile (LIFO).
        self.history = []
        # Limite de taille en octets pour l'historique compressé. Si la
        # somme de la taille des entrées dépasse cette valeur, les plus
        # anciennes seront supprimées. Cette valeur peut être ajustée au
        # besoin. Par exemple : 4000 octets.
        self.history_size_limit = 4000
        # Lancement de la boucle de jeu
        self.main_loop()

    def main_loop(self):
        """Boucle principale gérant l'affichage et les contrôles.

        Contrairement à la version d'origine, cette boucle ne bloque pas
        l'exécution en attendant que les touches soient relâchées. Elle
        teste en permanence l'état des touches et répète l'action
        associée tant que la touche reste enfoncée. Une courte pause est
        insérée après chaque action pour limiter la vitesse de
        répétition.
        """
        # Afficher la grille initiale
        self.print_map()
        # Délai de répétition en secondes (ajustable). Utiliser un float
        # avec ``time.sleep`` rend le script compatible avec MicroPython
        # sur NumWorks qui n'expose pas toujours ``sleep_ms``.
        repeat_delay = 0.25  # délai augmenté à 0,25 s selon demande
        # Boucle infinie : le jeu tourne tant que le script n'est pas interrompu
        while True:
            # Afficher le curseur à chaque itération afin de mettre à jour
            # l'aspect de la case sélectionnée (couleur différente)
            self.cursor.print_cursor()
            # Gestion spécifique de la touche OK : on ne déclenche l'action
            # ``click`` que lors de la transition de relâché vers enfoncé.
            current_ok = keydown(KEY_OK)
            if current_ok and not self._ok_last_state:
                # Première pression détectée : on inverse l'état de la case
                self.cursor.click()
                # Petite pause pour éviter de déclencher immédiatement d'autres actions
                time.sleep(repeat_delay)
                # Mettre à jour l'état précédent et passer à l'itération suivante
                self._ok_last_state = current_ok
                continue
            # Mettre à jour l'état précédent de la touche OK pour la détection
            self._ok_last_state = current_ok

            # Lecture des autres touches dans un ordre de priorité. Dès qu'une
            # condition est vraie, l'action est exécutée puis on attend
            # ``repeat_delay``. Si aucune touche n'est pressée, une pause plus
            # courte est effectuée pour alléger le processeur.
            if keydown(KEY_BACKSPACE):
                self.clear_map()
                time.sleep(repeat_delay)
            elif keydown(KEY_EXE):
                self.update_map()
                time.sleep(repeat_delay)
            elif keydown(KEY_MINUS):
                # Revenir à la génération précédente
                self.undo_map()
                time.sleep(repeat_delay)
            elif keydown(KEY_ANS):
                self.random_map()
                time.sleep(repeat_delay)
            elif keydown(KEY_UP):
                self.cursor.move_up()
                time.sleep(repeat_delay)
            elif keydown(KEY_DOWN):
                self.cursor.move_down()
                time.sleep(repeat_delay)
            elif keydown(KEY_LEFT):
                self.cursor.move_left()
                time.sleep(repeat_delay)
            elif keydown(KEY_RIGHT):
                self.cursor.move_right()
                time.sleep(repeat_delay)
            else:
                # Aucune touche n'est enfoncée, petite pause pour éviter un
                # sondage trop rapide et libérer de la puissance de calcul
                time.sleep(0.01)

    def update_map(self):
        """Calcule la génération suivante du jeu de la vie."""
        # Sauvegarder l'état actuel avant de calculer la nouvelle génération.
        # Cette méthode gère automatiquement les problèmes de mémoire en
        # supprimant les états les plus anciens si nécessaire.
        self._save_current_state()
        # Construire la nouvelle grille suivant les règles du jeu de la vie
        new_map = [[False] * len(self.map[0]) for _ in range(len(self.map))]
        for x in range(len(self.map)):
            for y in range(len(self.map[0])):
                neighbors = self.count_neighbors(x, y)
                new_map[x][y] = (neighbors == 2 or neighbors == 3) if self.map[x][y] else neighbors == 3
        self.map = new_map
        self.print_map()

    def count_neighbors(self, x, y):
        """Compte le nombre de voisins vivants autour de la cellule (x, y)."""
        count = 0
        rows, cols = len(self.map), len(self.map[0])
        for i in range(-1, 2):
            for j in range(-1, 2):
                if i == 0 and j == 0:
                    continue
                new_x, new_y = x + i, y + j
                if 0 <= new_x < rows and 0 <= new_y < cols:
                    count += self.map[new_x][new_y]
        return count

    def clear_map(self):
        """Réinitialise la grille en mettant toutes les cellules à l'état mort."""
        self.map = [[False] * self.num_of_cases_in_y for _ in range(self.num_of_cases_in_x)]
        # Vider l'historique car il n'a plus de sens après une réinitialisation
        self.history = []
        self.print_map()

    def random_map(self):
        """Remplit la grille avec un état aléatoire pour chaque cellule."""
        for x in range(self.num_of_cases_in_x):
            for y in range(self.num_of_cases_in_y):
                self.map[x][y] = bool(getrandbits(1))
        # Vider l'historique lors du remplissage aléatoire car l'historique
        # précédent ne correspond plus à cette nouvelle configuration.
        self.history = []
        self.print_map()

    def _save_current_state(self):
        """Enregistre une version compressée de la grille actuelle dans l'historique.

        La grille est convertie en une liste de ``bytes`` représentant
        chaque ligne. Cette représentation compacte divise la consommation
        mémoire en regroupant 8 cellules par octet. En cas de
        ``MemoryError`` lors de la compression ou de l'enregistrement,
        les entrées les plus anciennes de l'historique sont supprimées
        jusqu'à ce que l'opération réussisse ou que l'historique soit vide.
        """
        # Essayer de libérer un peu de mémoire avant la sauvegarde
        if gc:
            try:
                gc.collect()
            except Exception:
                pass
        while True:
            try:
                # Convertir la grille actuelle en représentation compacte
                compressed = self._compress_current_map()
                # Ajouter à l'historique
                self.history.append(compressed)
                # Vérifier que la taille totale de l'historique ne dépasse pas
                # la limite définie et supprimer les plus anciennes entrées si
                # nécessaire
                self._enforce_history_limit()
                return
            except MemoryError:
                # En cas d'erreur mémoire, supprimer l'entrée la plus ancienne
                if self.history:
                    self.history.pop(0)
                    if gc:
                        try:
                            gc.collect()
                        except Exception:
                            pass
                    continue
                else:
                    # Impossible de sauvegarder : abandonner
                    if gc:
                        try:
                            gc.collect()
                        except Exception:
                            pass
                    return

    def _compress_current_map(self):
        """Compacte la grille en une liste de lignes codées sur des octets.

        Chaque ligne de la grille (indexée par la coordonnée y) est
        transformée en une séquence de nombres compris entre 0 et 255
        (``bytes``). Chaque bit de ces nombres représente l'état d'une
        cellule (1 pour vivante, 0 pour morte). La largeur de la grille
        peut ne pas être un multiple de 8 ; les bits inutilisés du
        dernier octet sont positionnés à 0.

        Retourne une liste de ``bytes`` où chaque élément représente
        l'ensemble des cellules d'une ligne.
        """
        width = self.num_of_cases_in_x
        height = self.num_of_cases_in_y
        comp_rows = []
        for y in range(height):
            bit_count = 0
            byte_val = 0
            row_bytes = []
            for x in range(width):
                # Ajouter le bit courant
                byte_val = (byte_val << 1) | (1 if self.map[x][y] else 0)
                bit_count += 1
                if bit_count == 8:
                    row_bytes.append(byte_val)
                    bit_count = 0
                    byte_val = 0
            # Ajouter le dernier octet si la ligne n'est pas multiple de 8
            if bit_count > 0:
                byte_val = byte_val << (8 - bit_count)
                row_bytes.append(byte_val)
            # Convertir la liste d'entiers en objet bytes pour économiser la mémoire
            comp_rows.append(bytes(row_bytes))
        return comp_rows

    def _decompress_map(self, comp_rows):
        """Décompresse une représentation compacte d'une grille en une liste de listes de booléens.

        ``comp_rows`` doit être une liste où chaque élément est un objet
        ``bytes`` décrivant l'état d'une ligne : chaque bit représente
        une cellule. Les octets sont lus du bit de poids fort au bit de
        poids faible.

        Retourne une nouvelle grille au format [[bool]*hauteur] sur la
        dimension x,y (identique à ``self.map``)."""
        width = self.num_of_cases_in_x
        height = self.num_of_cases_in_y
        # Créer une grille vide
        new_map = [[False] * height for _ in range(width)]
        for y in range(height):
            row_bytes = comp_rows[y]
            bit_index = 0
            for byte_val in row_bytes:
                for bit_pos in range(7, -1, -1):
                    if bit_index < width:
                        new_map[bit_index][y] = ((byte_val >> bit_pos) & 1) == 1
                        bit_index += 1
                # Les bits restants sont ignorés
            # bit_index est réinitialisé automatiquement à chaque y
        return new_map

    def _enforce_history_limit(self):
        """Supprime les entrées les plus anciennes si la taille totale de l'historique dépasse la limite.

        Le seuil est défini par ``self.history_size_limit``. La taille est
        calculée comme la somme des longueurs (en octets) de chaque ligne
        compressée de toutes les grilles de l'historique. Si cette somme
        dépasse la limite, on dépile les entrées les plus anciennes jusqu'à
        revenir sous le seuil.
        """
        # Aucun seuil défini : rien à faire
        if self.history_size_limit is None:
            return
        # Calculer la taille totale des octets stockés
        total = 0
        for comp_map in self.history:
            for row in comp_map:
                total += len(row)
        # Supprimer les entrées les plus anciennes si nécessaire
        modified = False
        while total > self.history_size_limit and self.history:
            oldest = self.history.pop(0)
            # Soustraire la taille de l'entrée supprimée
            for row in oldest:
                total -= len(row)
            modified = True
        # Exécuter un ramassage si des entrées ont été supprimées
        if modified and gc:
            try:
                gc.collect()
            except Exception:
                pass

    def undo_map(self):
        """Revenir à la génération précédente si elle existe.

        On dépile la dernière grille enregistrée dans ``self.history`` et
        on l'affiche. Si l'historique est vide, la fonction ne fait rien.
        """
        if self.history:
            # Récupérer la représentation compressée la plus récente
            previous = self.history.pop()
            # Décompresser pour obtenir la grille complète
            self.map = self._decompress_map(previous)
            # Réafficher la grille
            self.print_map()

    def print_map(self):
        """Affiche la grille sur l'écran."""
        # Dessin des lignes de la grille
        for i in range(0, self.screen_size[0], self.size_of_case):
            fill_rect(i, 0, 1, self.screen_size[1], self.colors["gridColor"])
        for i in range(0, self.screen_size[1], self.size_of_case):
            fill_rect(0, i, self.screen_size[0], 1, self.colors["gridColor"])
        # Dessin des cases (vivantes ou mortes)
        for x in range(self.num_of_cases_in_x):
            for y in range(self.num_of_cases_in_y):
                fill_rect(
                    x * self.size_of_case + 1,
                    y * self.size_of_case + 1,
                    self.size_of_case - 1,
                    self.size_of_case - 1,
                    self.colors["blackColor"] if self.map[x][y] else self.colors["whiteColor"],
                )


class Cursor:
    def __init__(self, game):
        self.game = game
        # Position du curseur [x, y] en coordonnées de case
        self.location = [0, 0]

    def move_up(self):
        if self.location[1] != 0:
            self.reset_case()
            self.location[1] -= 1
        self.print_cursor()

    def move_down(self):
        if self.location[1] != self.game.num_of_cases_in_y - 1:
            self.reset_case()
            self.location[1] += 1
        self.print_cursor()

    def move_left(self):
        if self.location[0] != 0:
            self.reset_case()
            self.location[0] -= 1
        self.print_cursor()

    def move_right(self):
        if self.location[0] != self.game.num_of_cases_in_x - 1:
            self.reset_case()
            self.location[0] += 1
        self.print_cursor()

    def click(self):
        # Inverser l'état de la cellule sélectionnée
        self.game.map[self.location[0]][self.location[1]] = not self.game.map[self.location[0]][
            self.location[1]
        ]
        self.print_cursor()

    def reset_case(self):
        # Redessine la case sous le curseur avec sa couleur normale (vivante ou morte)
        fill_rect(
            self.location[0] * self.game.size_of_case + 1,
            self.location[1] * self.game.size_of_case + 1,
            self.game.size_of_case - 1,
            self.game.size_of_case - 1,
            self.game.colors["blackColor"]
            if self.game.map[self.location[0]][self.location[1]]
            else self.game.colors["whiteColor"],
        )

    def print_cursor(self):
        # Dessine le curseur avec une couleur différente selon l'état de la cellule
        fill_rect(
            self.location[0] * self.game.size_of_case + 1,
            self.location[1] * self.game.size_of_case + 1,
            self.game.size_of_case - 1,
            self.game.size_of_case - 1,
            self.game.colors["cursorBlackColor"]
            if self.game.map[self.location[0]][self.location[1]]
            else self.game.colors["cursorWhiteColor"],
        )


# Lorsque le script est lancé depuis l'application Python de la
# calculatrice, le code placé en dehors des définitions est exécuté
# immédiatement. On demande la taille des cases puis on lance le jeu.
try:
    size_of_case = int(input("Taille des cases : "))
except Exception:
    # Valeur par défaut si la saisie n'est pas un entier valide
    size_of_case = 10
Game(size_of_case)