# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2025-07-29

### Added

- **HDR10+DV Hybrid Processing**: New `-r HYBRID` command for processing HDR10 and Dolby Vision tracks
  - Support for hybrid HDR processing and injection using dovi_tool
  - New hybrid track processing module for seamless HDR10/DV conversion
  - Automatic detection and handling of HDR10 and DV metadata
- Support for HDR10 and DV tracks in hybrid mode for EXAMPLE service
- Binary availability check for dovi_tool in hybrid mode operations
- Enhanced track processing capabilities for HDR content

### Fixed

- Import order issues and missing json import in hybrid processing
- UV installation process and error handling improvements
- Binary search functionality updated to use `binaries.find`

### Changed

- Updated package version from 1.0.2 to 1.1.0
- Enhanced dl.py command processing for hybrid mode support
- Improved core titles (episode/movie) processing for HDR content
- Extended tracks module with hybrid processing capabilities
