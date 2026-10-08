<?php
/**
 * Plugin Name: Publi2.0: auth para API REST
 * Description: Permite que el pipeline de Publi2.0 publique por la API REST con contraseña de aplicación en servidores que borran el encabezado Authorization (LiteSpeed, FastCGI) o con plugins que consultan el usuario antes de tiempo. No abre acceso nuevo: sin contraseña de aplicación válida todo sigue rechazado.
 * Version: 1.1
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

// 1. Credencial alterna: X-Publi20-Auth lleva el mismo "Basic base64(usuario:contraseña)".
if ( empty( $_SERVER['PHP_AUTH_USER'] ) ) {
	$publi20_header = '';
	if ( ! empty( $_SERVER['HTTP_X_PUBLI20_AUTH'] ) ) {
		$publi20_header = $_SERVER['HTTP_X_PUBLI20_AUTH'];
	} elseif ( ! empty( $_SERVER['HTTP_AUTHORIZATION'] ) ) {
		$publi20_header = $_SERVER['HTTP_AUTHORIZATION'];
	} elseif ( ! empty( $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ) ) {
		$publi20_header = $_SERVER['REDIRECT_HTTP_AUTHORIZATION'];
	}
	$publi20_header = trim( (string) $publi20_header );
	if ( 0 === stripos( $publi20_header, 'basic ' ) ) {
		$publi20_decoded = base64_decode( substr( $publi20_header, 6 ), true );
		if ( false !== $publi20_decoded && false !== strpos( $publi20_decoded, ':' ) ) {
			list( $publi20_user, $publi20_pass ) = explode( ':', $publi20_decoded, 2 );
			$_SERVER['PHP_AUTH_USER'] = $publi20_user;
			$_SERVER['PHP_AUTH_PW']   = $publi20_pass;
		}
	}
}

// 2. Reconocer peticiones a la API REST desde el inicio, aunque otro plugin
//    consulte el usuario actual antes de que WordPress defina REST_REQUEST.
add_filter(
	'application_password_is_api_request',
	function ( $is_api_request ) {
		if ( $is_api_request ) {
			return true;
		}
		$uri = isset( $_SERVER['REQUEST_URI'] ) ? (string) $_SERVER['REQUEST_URI'] : '';
		return false !== strpos( $uri, '/wp-json/' ) || isset( $_GET['rest_route'] );
	}
);

// 3. Si alguien ya fijó el usuario como "anónimo" antes de tiempo, recalcularlo
//    al iniciar la API REST, cuando la contraseña de aplicación sí se evalúa.
add_action(
	'rest_api_init',
	function () {
		if ( ! empty( $_SERVER['PHP_AUTH_USER'] ) && 0 === get_current_user_id() ) {
			$GLOBALS['current_user'] = null;
			wp_get_current_user();
		}
	},
	0
);
