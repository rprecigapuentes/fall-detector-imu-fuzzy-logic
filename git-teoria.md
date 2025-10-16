# Fundamentos prácticos de Git (trabajo en equipo)

## 1. Qué pasa cuando creas una rama
Al crear una rama (`git checkout -b feature/x`) haces una **copia lógica** del proyecto dentro del historial local.  
No duplica los archivos físicamente: solo le dices a Git “desde ahora escribo en esta línea del tiempo alternativa”.  
Luego puedes fusionar esa rama con `main` para combinar los cambios.

- `main` → versión estable del proyecto  
- `feature/x` → espacio de trabajo paralelo para nuevas funciones

---

## 2. Qué hace `git add`
`git add` **selecciona qué archivos** vas a incluir en tu próximo commit.  
No guarda nada todavía; solo los deja listos en el *staging area*.

Ejemplo:
```bash
git add sensor.py
```
Ahora `sensor.py` será parte del próximo commit.

---

## 3. Qué hace `git commit`
`commit` **guarda una instantánea local** de los archivos que añadiste con `add`.  
Cada commit representa un punto de control en la historia.  
Aún no se ha subido a internet.

Secuencia típica:
```bash
git add archivo.py
git commit -m "feat: implementa lectura del sensor"
```

---

## 4. Qué es un Pull Request (PR)
Un PR **no es un comando de Git**, sino una función de plataformas como GitHub o GitLab.  
Sirve para decir:  
> “Revisen mi rama y, si está todo bien, mézclenla con main.”

Los pasos previos son:
1. `add` → seleccionas los cambios.
2. `commit` → guardas la foto localmente.
3. `push` → subes la rama al remoto.
4. En la web creas el **Pull Request**.

---

## 5. Qué hace `git fetch`
Descarga información del remoto (nuevos commits, ramas, tags) **sin modificar tu código local**.  
Actualiza el mapa, pero no tu directorio de trabajo.

```bash
git fetch origin
```

---

## 6. Qué hace `git rebase`
`rebase` **pone tus commits encima de los nuevos commits de otra rama**, manteniendo una historia limpia.  
Ejemplo:  
```bash
git rebase origin/main
```
Esto actualiza tu rama con los cambios recientes de `main` antes de subirlos.

Se usa después de terminar tus cambios y antes de hacer `push` o abrir un PR.

---

## 7. Qué hace `git push`
`push` **sube tus commits locales al servidor remoto**.  
Si estás en `feature/x`, sube esa rama.  
No crea automáticamente el PR; eso lo haces en la interfaz web.

```bash
git push -u origin feature/x
```

---

## 8. Qué pasa al hacer un PR
GitHub compara tu rama con `main`, muestra los cambios, permite comentarios y revisiones, y al final fusiona (merge o squash) tus commits en `main`.

---

## 9. Evitar pushes directos a `main`
Protege la rama principal:
> Settings → Branches → Add rule → “main”  
Activa:
- Require pull request before merging  
- Require review  
- Block direct pushes

Así evitas catástrofes tipo “borré medio repo sin querer”.

---

## 10. Sincronizar un PR
Si otro actualizó `main` mientras trabajabas, tu rama queda desfasada.  
Para actualizarla:
```bash
git fetch origin
git rebase origin/main
git push --force-with-lease
```
Esto alinea tu rama con la nueva versión de `main` sin crear merges extraños.

---

## 11. Qué hace `git revert`
`revert` **no borra commits**, crea un commit nuevo que deshace otro.

```bash
git revert <hash>
```
Se usa para revertir errores en `main` sin romper la historia.

---

## 12. Resumen rápido

| Acción | Qué hace | Dónde actúa |
|--------|-----------|-------------|
| `add` | Marca archivos para el próximo commit | Local |
| `commit` | Guarda un punto en la historia | Local |
| `fetch` | Trae info nueva del remoto | Local |
| `rebase` | Reorganiza tus commits encima de otra rama | Local |
| `push` | Sube tus commits al remoto | Remoto |
| `pull` | `fetch` + `merge` o `rebase` | Local |
| `revert` | Crea un commit que deshace otro | Local/Remoto |
| **PR** | Solicitud de fusión entre ramas | En la web |

---

## 13. Idea general
Usar Git bien no es memorizar comandos:  
es **entender que manejas una línea de tiempo compartida**.

- Commits = eventos en el tiempo  
- Ramas = universos paralelos  
- Rebase = alinear las líneas del tiempo  
- Merge = unirlas de nuevo  
- PR = pedir permiso antes de fusionar

---

### Secuencia típica en equipo

```bash
# 1. Actualiza main
git checkout main
git pull --rebase origin main

# 2. Crea tu rama de trabajo
git checkout -b feature/tu-rama

# 3. Cambia, añade y commitea
git add .
git commit -m "feat: descripción breve"

# 4. Rebase antes de subir
git fetch origin
git rebase origin/main

# 5. Sube tu rama y abre el PR
git push -u origin feature/tu-rama
```

## Gitignore

touch .gitignore
