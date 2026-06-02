(function($) {
    'use strict';

    $(window).on('elementor/frontend/init', function() {
        elementorFrontend.hooks.addAction('frontend/element_ready/dynamic_marquee_widget.default', function($scope) {
            var $widget = $scope.find('.dynamic-marquee-widget');
            var $list = $widget.find('.lista_marquee');
            var speed = $widget.data('speed');

            function setupMarquee() {
                var listWidth = $list.width();
                var containerWidth = $widget.width();
                var originalItems = $list.html();

                // Limpar a lista
                $list.empty();

                // Adicionar os itens originais
                $list.append(originalItems);

                // Continuar adicionando itens até preencher mais que o dobro da largura do container
                while ($list.width() < containerWidth * 2) {
                    $list.append(originalItems);
                }

                // Ajustar a animação CSS
                var totalWidth = $list.width() / 2;
                var duration = (totalWidth / containerWidth) * speed;

                $list.css({
                    'animation': 'none',
                    'transform': 'translateX(0)'
                });

                setTimeout(function() {
                    $list.css({
                        'animation': 'marquee ' + duration + 's linear infinite',
                        'transform': 'translateX(' + (-totalWidth) + 'px)'
                    });
                }, 100);
            }

            setupMarquee();
            $(window).on('resize', setupMarquee);
        });
    });

})(jQuery);
