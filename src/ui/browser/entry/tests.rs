// SPDX-License-Identifier: MIT

use super::{catppuccin, icon_for_name};
use crate::assets::icons;

#[test]
fn file_categories_and_case_insensitive_extensions() {
    for (name, icon) in [
        ("song.mp3", icons::FILE_AUDIO),
        ("take.WAV", icons::FILE_AUDIO),
        ("photo.png", icons::PICTURES),
        ("movie.mp4", icons::VIDEOS),
        ("video.mpeg", icons::VIDEOS),
        ("video.mpg", icons::VIDEOS),
        ("video.ogv", icons::VIDEOS),
        ("video.3gp", icons::VIDEOS),
        ("video.3g2", icons::VIDEOS),
        ("video.flv", icons::VIDEOS),
        ("video.wmv", icons::VIDEOS),
        ("video.asf", icons::VIDEOS),
        ("video.m2ts", icons::VIDEOS),
        ("video.vob", icons::VIDEOS),
        ("page.html", catppuccin::HTML),
        ("mailing.mjml", catppuccin::MJML),
        ("view.twig", catppuccin::TWIG),
        ("style.scss", catppuccin::SASS),
        ("feed.xml", catppuccin::XML),
        ("schema.xsd", catppuccin::XML),
        ("backup.zip", icons::FILE_ARCHIVE),
        ("backup.tar.gz", icons::FILE_ARCHIVE),
        ("backup.tgz", icons::FILE_ARCHIVE),
        ("backup.lz", icons::FILE_ARCHIVE),
        ("backup.lzma", icons::FILE_ARCHIVE),
        ("backup.lzo", icons::FILE_ARCHIVE),
        ("backup.rz", icons::FILE_ARCHIVE),
        ("backup.sz", icons::FILE_ARCHIVE),
        ("backup.cab", icons::FILE_ARCHIVE),
        ("backup.arj", icons::FILE_ARCHIVE),
        ("backup.cpio", icons::FILE_ARCHIVE),
        ("installer.AppImage", icons::BOX),
        ("app.apk", catppuccin::ANDROID),
        ("server.key", icons::KEY_ROUND),
        ("certificate.p12", icons::KEY_ROUND),
        ("config.toml", catppuccin::TOML),
        (".env", catppuccin::ENV),
        ("data.json", catppuccin::JSON),
        ("data.jsonc", catppuccin::JSON),
        ("data.jsonl", catppuccin::JSON),
        ("schema.proto", catppuccin::PROTO),
        ("query.sql", catppuccin::DATABASE),
        ("dump.parquet", catppuccin::DATABASE),
        ("app.nim", catppuccin::NIM),
        ("app.cr", catppuccin::CRYSTAL),
        ("app.rkt", catppuccin::RACKET),
        ("app.fs", catppuccin::FSHARP),
        ("view.qml", icons::FILE_CODE),
        ("flake.nix", catppuccin::NIX),
        ("note.ipynb", catppuccin::JUPYTER),
        ("data.sqlite3", catppuccin::DATABASE),
        ("disk.iso", icons::DISC),
        ("data.tsv", icons::FILE_SPREADSHEET),
        ("sheet.xlsx", icons::FILE_SPREADSHEET),
        ("main.rs", catppuccin::RUST),
        ("main.hpp", catppuccin::CPP_HEADER),
        ("main.c", catppuccin::C),
        ("app.py", catppuccin::PYTHON),
        ("app.pyw", catppuccin::PYTHON),
        ("app.js", catppuccin::JAVASCRIPT),
        ("app.jsx", catppuccin::JAVASCRIPT_REACT),
        ("app.mjs", catppuccin::JAVASCRIPT),
        ("app.ts", catppuccin::TYPESCRIPT),
        ("app.tsx", catppuccin::TYPESCRIPT_REACT),
        ("app.mts", catppuccin::TYPESCRIPT),
        ("main.go", catppuccin::GO),
        ("Main.java", catppuccin::JAVA),
        ("Main.kt", catppuccin::KOTLIN),
        ("build.kts", catppuccin::KOTLIN),
        ("app.swift", catppuccin::SWIFT),
        ("app.dart", catppuccin::DART),
        ("app.scala", catppuccin::SCALA),
        ("app.hs", catppuccin::HASKELL),
        ("app.lua", catppuccin::LUA),
        ("app.cs", catppuccin::CSHARP),
        ("app.r", catppuccin::R),
        ("app.jl", catppuccin::JULIA),
        ("app.ex", catppuccin::ELIXIR),
        ("app.exs", catppuccin::ELIXIR),
        ("app.erl", catppuccin::ERLANG),
        ("app.zig", catppuccin::ZIG),
        ("app.vue", catppuccin::VUE),
        ("app.svelte", catppuccin::SVELTE),
        ("app.astro", catppuccin::ASTRO),
        ("app.elm", catppuccin::ELM),
        ("app.rb", catppuccin::RUBY),
        ("view.erb", catppuccin::RUBY),
        ("index.php", catppuccin::PHP),
        ("app.pl", catppuccin::PERL),
        ("app.ml", catppuccin::OCAML),
        ("app.clj", catppuccin::CLOJURE),
        ("app.groovy", catppuccin::GROOVY),
        ("main.tf", catppuccin::TERRAFORM),
        ("schema.graphql", catppuccin::GRAPHQL),
        ("token.sol", catppuccin::SOLIDITY),
        ("notes.m", catppuccin::MATLAB),
        ("notes.v", catppuccin::V),
        ("boot.s", catppuccin::ASSEMBLY),
        ("app.tcl", icons::FILE_CODE),
        ("app.jsp", catppuccin::JAVA),
        ("app.jar", catppuccin::JAVA_JAR),
        ("lib.o", icons::BOX),
        ("pkg.crate", icons::BOX),
        ("build.cmake", catppuccin::CMAKE),
        ("settings.cfg", catppuccin::PROPERTIES),
        ("Rakefile", catppuccin::RUBY),
        ("Vagrantfile", catppuccin::RUBY),
        ("Justfile", catppuccin::JUST),
        (".env.local", catppuccin::ENV),
        (".rprofile", catppuccin::R),
        ("run.ps1", catppuccin::POWERSHELL),
        ("run.bash", catppuccin::BASH),
        ("report.DOCX", icons::DOCUMENTS),
        ("report.odt", icons::DOCUMENTS),
        ("deck.pptx", icons::PRESENTATION),
        ("deck.odp", icons::PRESENTATION),
        ("README.md", catppuccin::README),
        ("font.woff2", icons::FILE_TYPE),
        ("doc.pdf", icons::DOCUMENTS),
    ] {
        assert_eq!(icon_for_name(name), icon, "file: {name}");
    }
}

#[test]
fn exact_names_override_extensions_without_matching_backups() {
    for (name, icon) in [
        ("package-lock.json", catppuccin::NPM_LOCK),
        ("pnpm-lock.yaml", catppuccin::PNPM_LOCK),
        ("CMakeLists.txt", catppuccin::CMAKE),
        ("Cargo.lock", catppuccin::CARGO_LOCK),
        (".BASHRC", catppuccin::BASH),
        (".zprofile", catppuccin::BASH),
        (".gitignore", catppuccin::GIT),
        (".XCompose", catppuccin::CONFIG),
        ("Makefile", catppuccin::MAKEFILE),
        ("Dockerfile", catppuccin::DOCKER),
        ("id_ed25519", icons::KEY_ROUND),
        ("known_hosts", icons::KEY_ROUND),
        ("README", catppuccin::README),
        ("LICENSE", catppuccin::LICENSE),
        (".bashrc.distro-upgrade.done.bak", icons::DOCUMENTS),
        (".bash_history.bak", icons::DOCUMENTS),
        ("id_rsa.bak", icons::DOCUMENTS),
        ("Dockerfile.bak", catppuccin::DOCKER),
    ] {
        assert_eq!(icon_for_name(name), icon, "file: {name}");
    }
}

#[test]
fn filename_patterns_override_suffixes_and_respect_casing() {
    for (name, icon) in [
        ("Dockerfile.txt", catppuccin::DOCKER),
        ("Dockerfile.dev", catppuccin::DOCKER),
        ("tsconfig.json", catppuccin::TYPESCRIPT_CONFIG),
        ("tsconfig.base.json", catppuccin::TYPESCRIPT_CONFIG),
        ("tsconfig.base.json.bak", icons::DOCUMENTS),
        ("other-tsconfig.json", catppuccin::JSON),
        (".bash_history", icons::FILE_TERMINAL),
        (".BASH_HISTORY", icons::DOCUMENTS),
        ("yarn.lock", catppuccin::YARN_LOCK),
        ("poetry.lock", catppuccin::POETRY_LOCK),
    ] {
        assert_eq!(icon_for_name(name), icon, "file: {name}");
    }
}

#[test]
fn unknown_files_preserve_the_document_fallback() {
    for name in ["notes.xyz", "randomfile", "archive.???", "", "trailing."] {
        assert_eq!(icon_for_name(name), icons::DOCUMENTS, "file: {name}");
    }
}

#[test]
fn catppuccin_associations_prefer_longest_suffix_and_exact_names() {
    for (name, icon) in [
        ("types.d.ts", catppuccin::TYPESCRIPT_DEF),
        ("app.test.ts", catppuccin::TYPESCRIPT_TEST),
        ("docker-compose.override.yml", catppuccin::DOCKER_COMPOSE),
        ("compose.yaml", catppuccin::DOCKER_COMPOSE),
        ("deploy.yml", catppuccin::YAML),
        ("package.json", catppuccin::PACKAGE_JSON),
        ("Cargo.toml", catppuccin::CARGO),
        ("rustfmt.toml", catppuccin::RUST_CONFIG),
        ("pyproject.toml", catppuccin::PYTHON_CONFIG),
        ("go.mod", catppuccin::GO_MOD),
        ("vite.config.ts", catppuccin::VITE),
        (".eslintrc.json", catppuccin::ESLINT),
        ("CHANGELOG.md", catppuccin::CHANGELOG),
        ("notes.md", catppuccin::MARKDOWN),
        ("ci.yml", catppuccin::YAML),
        ("archive.lock", icons::COG),
        ("photo.svg", icons::PICTURES),
        ("notes.txt", icons::DOCUMENTS),
        ("report.csv", icons::FILE_SPREADSHEET),
        ("server.pem", icons::KEY_ROUND),
    ] {
        assert_eq!(icon_for_name(name), icon, "file: {name}");
    }
}
